"""Safe GitHub import: URL allow-list, shallow clone into the workspace, size limits, git metadata.

Repository code is only ever read as text. It is never imported, executed or built.
"""
import logging
import os
import re
import shutil
import stat
from datetime import timezone
from pathlib import Path

from git import GitCommandError, Repo

from app.config import ROOT_DIR, settings
from app.errors import ImportFailure

log = logging.getLogger(__name__)
_GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100})$")
CLONE_DEPTH = 100          # bounded history: enough for commit/contributor analytics, small enough to be fast
CLONE_TIMEOUT_S = 300


def normalize_git_url(url: str) -> tuple[str, str]:
    """Return (canonical_url, repo_name) or raise ImportFailure. Only https://github.com/<owner>/<repo>."""
    candidate = (url or "").strip().rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    m = _GITHUB_RE.match(candidate)
    if not m or m.group(1) in (".", "..") or m.group(2) in (".", ".."):
        raise ImportFailure("Only public GitHub URLs like https://github.com/<owner>/<repo> are supported.")
    return candidate, m.group(2)


def workspace_root() -> Path:
    p = Path(settings.workspace_dir)
    p = p if p.is_absolute() else ROOT_DIR / p
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def repo_dir(repo_id: int) -> Path:
    """Workspace path for a repo. Built from the integer id only, and verified to stay inside the workspace."""
    root = workspace_root()
    path = (root / str(int(repo_id))).resolve()
    if root not in path.parents:
        raise ImportFailure("Invalid workspace path.")
    return path


def _rmtree(path: Path) -> None:
    """rmtree that also removes read-only files (git object files are read-only on Windows)."""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onexc=_retry)


def remove_repo_dir(repo_id: int) -> None:
    _rmtree(repo_dir(repo_id))


def _dir_size_mb(path: Path) -> float:
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            pass
    return total / (1024 * 1024)


def clone_repo(git_url: str, repo_id: int) -> Repo:
    dest = repo_dir(repo_id)
    _rmtree(dest) if dest.exists() else None
    env = {
        "GIT_TERMINAL_PROMPT": "0",          # never block asking for credentials
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "core.symlinks", "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "core.hooksPath", "GIT_CONFIG_VALUE_1": str(dest.parent / "_no_hooks"),
    }
    try:
        extra = {} if os.name == "nt" else {"kill_after_timeout": CLONE_TIMEOUT_S}   # unsupported on Windows
        repo = Repo.clone_from(git_url, dest, depth=CLONE_DEPTH, single_branch=True, no_tags=True,
                               env=env, **extra)
    except GitCommandError as exc:
        log.warning("git clone failed for repo %s: %s", repo_id, exc)
        _rmtree(dest) if dest.exists() else None
        raise ImportFailure("Could not clone the repository. Check that the URL exists and is public.")
    size = _dir_size_mb(dest)
    if size > settings.max_repo_size_mb:
        repo.close()
        _rmtree(dest)
        raise ImportFailure(f"Repository is {size:.0f} MB, above the {settings.max_repo_size_mb} MB limit.")
    return repo


def read_branch_info(repo: Repo) -> tuple[str, str | None]:
    """(default branch name, head commit hash)."""
    try:
        name = repo.active_branch.name
    except TypeError:                       # detached HEAD
        name = "HEAD"
    try:
        head = repo.head.commit.hexsha
    except ValueError:
        head = None
    return name, head


def read_commits(repo: Repo, limit: int = CLONE_DEPTH):
    """Yield dicts of commit metadata plus per-file changes.

    The oldest commit of a shallow clone has no parent in the clone, so a diff against it would be the
    whole tree; its additions/deletions/file changes are left empty instead of recording fake numbers.
    """
    for c in repo.iter_commits(max_count=limit):
        info = {
            "hash": c.hexsha,
            "message": (c.message or "").strip()[:10000],
            "committed_at": c.committed_datetime.astimezone(timezone.utc).replace(tzinfo=None),
            "additions": 0, "deletions": 0, "files": [],
        }
        if c.parents:
            try:
                stats = c.stats
                info["additions"], info["deletions"] = stats.total["insertions"], stats.total["deletions"]
                for d in c.parents[0].diff(c):
                    path = d.b_path or d.a_path
                    ctype = {"A": "added", "D": "deleted", "R": "renamed"}.get(d.change_type, "modified")
                    fs = stats.files.get(path, {})
                    info["files"].append((path, ctype, fs.get("insertions", 0), fs.get("deletions", 0)))
            except (GitCommandError, ValueError):
                pass
        yield info
