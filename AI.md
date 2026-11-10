# AI.md — GrepRight development handoff

Read this first every session. Update it at session end and on major decisions.

## Status
- **Current phase:** Phase 3 (embeddings + Qdrant + search API) — code written, **45/45 backend tests pass**, real FastEmbed model + Qdrant Cloud smoke-tested. Awaiting user review/approval before Phase 4.
- **Last updated:** 2026-11-10

## Project
Semantic code search platform. Next.js (**plain JavaScript, no TypeScript** — user decision 2026-11-08) + FastAPI + MySQL (source of truth) + Qdrant Cloud (vectors) + FastEmbed `BAAI/bge-small-en-v1.5` (384-d) + GitPython + Python `ast` / Tree-sitter. No Docker, no PyTorch, no LLM. Full spec: user's master instructions (phases 0–6); architecture/schema/API: `docs/ARCHITECTURE.md`.

## Hard rules
- Claude NEVER runs `git add/commit/push/branch/merge`, touches remotes, or creates PRs. Only inspect; suggest commit messages.
- Do not start next phase without user approval.
- Secrets only in `.env` (gitignored); keep `.env.example` current.
- Parameterized SQL only; never execute imported code.

## Environment (verified 2026-11-02)
Windows 11, Python 3.13.7, Node 22.19.0, npm 11.6.0, MySQL 8.0.46, git 2.53. Qdrant Cloud credentials are in `.env` (works, verified 2026-11-10).

## Done (Phase 0)
- Inspected repo: only `README.md` (2 lines) existed. No ER diagram / assignment brief found.
- Architecture, schema, API contract → `docs/ARCHITECTURE.md`.
- Created: `.gitignore`, `.env.example`, `backend/requirements.txt`, empty package skeleton (`backend/app/{api,services,db,parsers}`, `backend/tests`, `database/`, `frontend/`, `docs/`), `AI.md`, `CLAUDE.md`.

## Decisions
- **Schema = user's ER diagram / relational schema ONLY.** Any extra column/table needs justification + user approval. APPROVED additions (user, 2026-11-02): `users.role`, `repositories.status`+`error_message`, `audit_log` table, and `commits.branch_id` (from relational schema). Earlier extras (functions.class_id, embedded_at, renamed cols) are dropped.
- Qdrant point ID = `code_chunks.chunk_id`, stored in `embedding_ref`.
- Assignment brief read: needs auth + >=2 roles, DB-level validation, >=4 advanced concepts, data dictionary, screenshots, tests, per-member contributions.
- Raw SQL via mysql-connector-python (no ORM); background indexing via FastAPI BackgroundTasks.
- Junction tables: `repository_members`, `commit_files`.

## Done (Phase 1, 2026-11-02)
- `database/schema.sql`: 11 tables (10 ER tables + `audit_log`), approved extras (`users.role`, `repositories.status/error_message`, `commits.branch_id`). PK/FK (CASCADE; `repositories.owner_id` RESTRICT; `commits.branch_id`/`author_id` SET NULL), UNIQUE, CHECK (username length, email shape, github URL, line ranges), ENUMs, secondary indexes, FULLTEXT on `code_chunks.content`. Idempotent (`IF NOT EXISTS`).
- `backend/app/config.py` (pydantic-settings reads root `.env`), `db/connection.py` (pool, commit/rollback ctx mgr, execute/fetch_all/fetch_one), `db/init_db.py` (creates DB + applies schema), `db/repository.py` (parameterized CRUD for every table).
- `backend/tests/conftest.py` + `test_db.py`: 11 tests using throwaway DB `grepright_test` (dropped after run): CRUD, unique/PK/FK/CHECK/ENUM violations, cascade, SET NULL, RESTRICT, rollback, FULLTEXT presence.
- `backend/.venv` holds the installed deps (pydantic-settings, mysql-connector-python, pytest, fastapi, httpx, GitPython, tree-sitter*, fastembed, qdrant-client).

## Done (Phase 2, 2026-11-08)
- Parsers (`backend/app/parsers/`): `discovery.py` (walk, skip dirs/binaries/oversize/symlinks, LF-normalised read), `python_parser.py` (ast), `js_parser.py` (tree-sitter JS/TS/TSX), `chunker.py` (function/class-header/module chunks, 80-line windows), `models.py`, `__init__.py` (`parse_file`).
- Services: `importer.py` (GitHub URL allow-list, shallow clone depth 100 via GitPython, size cap, commit/branch reading), `indexer.py` (background job, in-memory progress, status in DB, clone deleted afterwards).
- API: `main.py` (CORS, error shape `{error:{code,message}}`, `/health`, restart recovery), `api/repositories.py` (POST/GET/DELETE repos, status, files, file detail), `errors.py`.
- DB: `repository.py` gained system-user, bulk file-bundle insert (one txn/file), counts, prefix file list, cleanup, restart recovery.
- Frontend (`frontend/`, JS only): Next.js 15 app router — home (import form + list), repo page (status polling, stats, file tree, delete), file page (symbols + chunks). `npm run build` passes.
- Tests: `test_parsers.py`, `test_import_api.py` (HTTP flow with local git repo standing in for the clone).

## Done (Phase 3, 2026-11-10)
- `services/embedder.py`: lazy FastEmbed, bge query prefix, embedding text = path+name+signature+docstring+code truncated to 2000 chars.
- `services/vector_store.py`: Qdrant cosine/384 collection, payload indexes (repo_id, file_id, language, chunk_type), upsert, filtered search, delete by repo_id, ping. `QDRANT_URL=:memory:` gives an in-process client (used by tests).
- `services/search.py`: embed query → Qdrant top-k → MySQL join → ranked results with snippet.
- Indexer: new `embed_repository` stage after git history (progress stage `embedding`); upserts batches, then sets `embedding_ref = chunk_id`. Any failure → repo status `failed`.
- API: `POST /api/search` (`api/search.py`; query ≤500 chars, limit 1–50, optional repo_id/language; 404 unknown repo, 503 if backend down). `DELETE repo` also deletes its Qdrant vectors (503 and MySQL row kept if Qdrant unreachable). `/health` reports real Qdrant status.
- DB helpers: `list_chunks_to_embed`, `count_chunks_to_embed`, `set_embedding_refs`, `get_chunks_with_context`. Chunk name = join of functions/classes on file_id + start_line (no schema change).
- `config.py`: `QDRANT_URL` doubled-scheme typo (`https:https://`) auto-normalised; new `embed_batch_size`, `max_embed_chars`. `.env` itself NOT edited.
- Tests: conftest forces `QDRANT_URL=:memory:` + a fake hash embedder (offline, fast); `test_search.py` has 7 tests. Real model + cloud verified by a manual smoke script (temporary collection created then deleted): dim 384, relevant doc ranked first.
- Model is cached on first use (~130 MB download).

## Decisions (Phase 2)
- No auth yet: imports are owned by a placeholder `system` admin user (`get_or_create_system_user`). Real auth/roles still TODO.
- `commits.author_id` stays NULL (git authors are not app users). `commit_files` only for files in the current tree; the oldest commit of the shallow clone gets no stats (would be a fake whole-tree diff).
- Only py/js/ts are parsed/chunked; other known text types are recorded in `files` only. Source isn't stored, so the file page shows symbols + chunks, not the full file.
- `kill_after_timeout` unsupported on Windows, so clone has no hard timeout there; size cap is checked after clone.

## Test results
`cd backend && .venv\Scripts\python -m pytest tests -q` → 45 passed (11 DB + 27 parser/import + 7 search). Phase 2 smoke: real import of pallets/click → 156 files, 1314 functions, 121 classes, 1624 chunks, 100 commits.

## Known issues / open questions
- `.env` `QDRANT_URL` still has a typo (`https:https://...`); code tolerates it, but please fix it. Do not commit `.env`.
- Full real import (real model + cloud collection `code_chunks`) not run yet, only the smoke script.
- `clear_repository_data` (retry of a failed import) does not purge Qdrant yet; search skips orphan vectors.
- Frontend not yet exercised in a browser against the live API (build only); no search UI yet (Phase 4).
- Relational-schema screenshot was cut off after `code_chunks.embedding_ref`; ask if more columns exist.

## Run commands
```
python -m venv backend/.venv && backend\.venv\Scripts\activate && pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend      # API :8000
cd frontend && npm run dev                            # UI :3000
```

## Next steps
1. USER: review Phase 3, fix `.env` URL, then approve Phase 4 (search UI / frontend).
2. Later: auth + roles, analytics (Phase 5 SQL), `docs/DATABASE.md`.

## Suggested commit message (Phase 3)
`feat: Phase 3 — FastEmbed embeddings, Qdrant vector store, semantic search API`
