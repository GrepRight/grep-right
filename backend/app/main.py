import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import repositories, search
from app.services import vector_store
from app.config import settings
from app.db import repository as r
from app.errors import AppError

log = logging.getLogger("grepright")


@asynccontextmanager
async def lifespan(app: FastAPI):
    r.fail_interrupted_repositories()
    yield


app = FastAPI(title="GrepRight", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(repositories.router)
app.include_router(search.router)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(AppError)
async def _app_error(_: Request, exc: AppError):
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    return _error(422, "validation_error", "Invalid request.")


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return _error(500, "internal_error", "Internal server error.")


@app.get("/health")
def health():
    try:
        r.fetch_one("SELECT 1 AS ok")
        mysql = "ok"
    except Exception:
        mysql = "error"
    try:
        qdrant = "ok" if vector_store.ping() else "error"
    except Exception:
        qdrant = "error"
    return {"status": "ok" if mysql == qdrant == "ok" else "degraded", "mysql": mysql, "qdrant": qdrant}
