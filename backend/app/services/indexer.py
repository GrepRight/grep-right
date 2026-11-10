"""Background import job: clone -> record branch/files/symbols/chunks/commits -> mark ready.

Runs inside a FastAPI BackgroundTask. Progress lives in memory; durable state is repositories.status.
After indexing, chunks are embedded (FastEmbed) and upserted to Qdrant; embedding_ref = chunk_id.
"""
import logging
import threading
from collections import Counter

from app.config import settings
from app.db import repository as r
from app.errors import ImportFailure
from app.parsers import build_chunks, parse_file
from app.parsers.discovery import PARSED_LANGUAGES, iter_source_files, read_source
from app.services import embedder, importer, vector_store

log = logging.getLogger(__name__)

_progress: dict[int, dict] = {}
_lock = threading.Lock()


def get_progress(repo_id: int) -> dict:
    with _lock:
        return dict(_progress.get(repo_id, {}))


def _set_progress(repo_id: int, **kw) -> None:
    with _lock:
        _progress.setdefault(repo_id, {"stage": "queued", "processed": 0, "total": 0}).update(kw)


def index_working_tree(repo_id: int, root) -> Counter:
    """Walk `root`, store every recordable file (+ symbols/chunks for parsed languages).

    Returns line counts per parsed language (used to pick primary_language).
    """
    files = list(iter_source_files(root, settings.max_file_size_kb * 1024))
    _set_progress(repo_id, stage="indexing", processed=0, total=len(files))
    lang_lines: Counter = Counter()
    for i, sf in enumerate(files, 1):
        try:
            source = read_source(sf.abs_path)
            line_count = source.count("\n") + (0 if source.endswith("\n") or not source else 1)
            symbols, chunks = [], []
            if sf.language in PARSED_LANGUAGES:
                parsed = parse_file(source, sf.language, sf.rel_path)
                symbols, chunks = parsed.symbols, build_chunks(source, parsed)
                lang_lines[sf.language] += line_count
            r.insert_file_bundle(repo_id, sf, line_count, symbols, chunks)
        except Exception:
            log.exception("Skipping file %s in repo %s", sf.rel_path, repo_id)
        _set_progress(repo_id, processed=i)
    return lang_lines


def store_git_history(repo_id: int, repo) -> None:
    branch_name, head = importer.read_branch_info(repo)
    branch_id = r.create_branch(repo_id, branch_name, head, True)
    file_map = r.get_file_map(repo_id)
    for c in importer.read_commits(repo):
        commit_id = r.create_commit(repo_id, c["hash"], branch_id=branch_id, message=c["message"],
                                    committed_at=c["committed_at"], additions=c["additions"],
                                    deletions=c["deletions"])
        for path, ctype, adds, dels in c["files"]:
            file_id = file_map.get(path)            # files absent from the current tree are not tracked
            if file_id:
                r.add_commit_file(commit_id, file_id, ctype, adds, dels)
    r.mark_repository_synced(repo_id, default_branch=branch_name)


def embed_repository(repo_id: int) -> int:
    """Embed every chunk of the repo that has no embedding_ref and upsert to Qdrant. Returns chunks embedded."""
    total = r.count_chunks_to_embed(repo_id)
    _set_progress(repo_id, stage="embedding", processed=0, total=total)
    if not total:
        return 0
    vector_store.ensure_collection()
    done, last_id = 0, 0
    while True:
        rows = r.list_chunks_to_embed(repo_id, last_id, settings.embed_batch_size * 4)
        if not rows:
            break
        vectors = embedder.embed_documents([embedder.chunk_text(row) for row in rows])
        vector_store.upsert([
            (row["chunk_id"], vec, {"repo_id": repo_id, "file_id": row["file_id"],
                                    "language": row["language"], "chunk_type": row["chunk_type"]})
            for row, vec in zip(rows, vectors)])
        r.set_embedding_refs([row["chunk_id"] for row in rows])   # only after Qdrant accepted the points
        last_id = rows[-1]["chunk_id"]
        done += len(rows)
        _set_progress(repo_id, processed=done)
    return done


def run_import(repo_id: int, git_url: str) -> None:
    """Entry point for the background task. Never raises; failures are recorded on the repository row."""
    repo = None
    try:
        _set_progress(repo_id, stage="cloning", processed=0, total=0)
        r.update_repository_status(repo_id, "cloning")
        repo = importer.clone_repo(git_url, repo_id)

        r.update_repository_status(repo_id, "indexing")
        lang_lines = index_working_tree(repo_id, importer.repo_dir(repo_id))
        store_git_history(repo_id, repo)
        embed_repository(repo_id)

        primary = lang_lines.most_common(1)[0][0] if lang_lines else None
        r.mark_repository_synced(repo_id, primary_language=primary)
        r.update_repository_status(repo_id, "ready")
        _set_progress(repo_id, stage="ready")
    except ImportFailure as e:
        r.update_repository_status(repo_id, "failed", str(e))
        _set_progress(repo_id, stage="failed")
    except Exception:
        log.exception("Import of repo %s failed", repo_id)
        r.update_repository_status(repo_id, "failed", "Import failed unexpectedly. See server logs.")
        _set_progress(repo_id, stage="failed")
    finally:
        if repo is not None:
            repo.close()                        # release git file handles (required before deleting on Windows)
        importer.remove_repo_dir(repo_id)      # the clone is only needed while indexing
