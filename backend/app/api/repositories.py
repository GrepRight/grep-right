import logging

from fastapi import APIRouter, BackgroundTasks, Query, Response
from pydantic import BaseModel

from app.db import repository as r
from app.errors import AppError, ImportFailure
from app.services import analytics, importer, indexer, vector_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["repositories"])

_BUSY = ("pending", "cloning", "indexing")


class ImportRequest(BaseModel):
    git_url: str


def _get_or_404(repo_id: int) -> dict:
    repo = r.get_repository(repo_id)
    if not repo:
        raise AppError(404, "repo_not_found", "Repository not found.")
    return repo


@router.post("/repositories", status_code=202)
def import_repository(body: ImportRequest, background: BackgroundTasks):
    try:
        url, name = importer.normalize_git_url(body.git_url)
    except ImportFailure as e:
        raise AppError(400, "invalid_url", str(e))
    existing = r.get_repository_by_url(url)
    if existing:
        if existing["status"] != "failed":
            raise AppError(409, "already_imported", "This repository has already been imported.")
        repo_id = existing["repo_id"]            # retry a failed import
        r.clear_repository_data(repo_id)
        r.update_repository_status(repo_id, "pending")
    else:
        repo_id = r.create_repository(r.get_or_create_system_user(), name, url)
    background.add_task(indexer.run_import, repo_id, url)
    return {"repo_id": repo_id}


@router.get("/repositories")
def list_repositories():
    return r.list_repositories()


@router.get("/repositories/{repo_id}")
def get_repository(repo_id: int):
    repo = _get_or_404(repo_id)
    repo["counts"] = r.get_repository_counts(repo_id)
    return repo


@router.get("/repositories/{repo_id}/status")
def get_status(repo_id: int):
    repo = _get_or_404(repo_id)
    progress = indexer.get_progress(repo_id)
    return {
        "status": repo["status"],
        "stage": progress.get("stage", repo["status"]),
        "processed": progress.get("processed", 0),
        "total": progress.get("total", 0),
        "error": repo["error_message"],
    }


@router.delete("/repositories/{repo_id}", status_code=204)
def delete_repository(repo_id: int):
    repo = _get_or_404(repo_id)
    if repo["status"] in _BUSY:
        raise AppError(409, "repo_busy", "Repository is being imported; try again when it finishes.")
    try:
        vector_store.delete_repo(repo_id)
    except Exception:
        log.exception("Could not delete vectors for repo %s", repo_id)
        raise AppError(503, "vector_store_unavailable", "Could not remove search vectors; try again later.")
    r.delete_repository(repo_id)                 # FK cascades remove files/symbols/chunks/commits/branches
    importer.remove_repo_dir(repo_id)
    return Response(status_code=204)


@router.get("/repositories/{repo_id}/files")
def list_files(repo_id: int, path: str = Query("", max_length=500)):
    _get_or_404(repo_id)
    return r.list_files_under(repo_id, path)


@router.get("/files/{file_id}")
def get_file(file_id: int):
    detail = r.get_file_detail(file_id)
    if not detail:
        raise AppError(404, "file_not_found", "File not found.")
    return detail


@router.get("/repositories/{repo_id}/analytics")
def get_analytics(repo_id: int):
    _get_or_404(repo_id)
    return analytics.get_analytics(repo_id)
