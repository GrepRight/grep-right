import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import repository as r
from app.errors import AppError
from app.services import search as search_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    repo_id: int | None = None
    language: str | None = Field(default=None, max_length=30)
    limit: int = Field(default=10, ge=1, le=50)


@router.post("/search")
def search(body: SearchRequest):
    query = body.query.strip()
    if not query:
        raise AppError(422, "validation_error", "Query must not be empty.")
    if body.repo_id is not None and not r.get_repository(body.repo_id):
        raise AppError(404, "repo_not_found", "Repository not found.")
    try:
        return search_service.search(query, body.repo_id, body.language, body.limit)
    except Exception:
        log.exception("Search failed")
        raise AppError(503, "search_unavailable", "Search is currently unavailable.")
