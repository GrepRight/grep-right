# GrepRight — Architecture (Phase 0)

## Overview

```
Next.js (JS) ──HTTP/JSON──> FastAPI ──> MySQL   (source of truth: metadata, chunks, analytics)
                               │
                               ├──> GitPython (clone to backend/workspace/, never executed)
                               ├──> Parsers: Python `ast`, Tree-sitter (JS/TS)
                               └──> FastEmbed (bge-small-en-v1.5, 384-d) ──> Qdrant Cloud (vectors + payload)
```

Search: query → FastEmbed → Qdrant top-k (cosine) → chunk_ids → MySQL join (chunk/file/repo) → ranked results.

**Stable ID link:** the Qdrant point ID is `code_chunks.chunk_id` (unsigned int). Payload holds `repo_id`, `file_id`, `language`, `chunk_type` for filtering. No separate UUID column.

## Directory layout

```
backend/app/{main.py,config.py}  FastAPI entry + settings (.env)
backend/app/api/                 routers (repositories, search, analytics)
backend/app/services/            importer, indexer, search, analytics
backend/app/parsers/             python_parser.py, js_parser.py, discovery.py
backend/app/db/                  connection, repository (SQL) functions
backend/tests/
database/                        schema.sql, views.sql, procedures.sql, triggers.sql, queries.sql
frontend/                        Next.js app
docs/                            architecture, schema, API, final report
```

## Relational schema (MySQL, InnoDB, utf8mb4) — follows the user's ER diagram ONLY

Rule (user, 2026-11-02): schema must match the ER diagram/relational schema exactly. Anything extra needs written justification and user approval (see "Proposed additions").

| Table | Columns (PK **bold**) |
|---|---|
| users | **user_id**, username, email, password_hash, created_at, last_login |
| repositories | **repo_id**, owner_id → users, name, description, git_url, default_branch, primary_language, created_at, last_synced_at |
| repository_members | **(user_id → users, repo_id → repositories)**, role, joined_at |
| branches | **branch_id**, repo_id → repositories, name, head_commit_hash, is_default |
| commits | **commit_id**, commit_hash, repo_id → repositories, branch_id → branches (*), author_id → users, message, committed_at, additions, deletions |
| files | **file_id**, repo_id → repositories, file_path, language, size_bytes, line_count, last_modified |
| commit_files | **(commit_id → commits, file_id → files)**, change_type, additions, deletions |
| functions | **func_id**, file_id → files, name, signature, start_line, end_line, docstring |
| classes | **class_id**, file_id → files, name, start_line, end_line, docstring |
| code_chunks | **chunk_id**, file_id → files, chunk_type, content, start_line, end_line, embedding_ref |

(*) `commits.branch_id` is in the user's relational schema but not drawn in the ER diagram — **approved, keep** (branch the commit was found on during import).

Not attributes, so no approval needed: UNIQUE (username, email, git_url, (repo_id,file_path), (repo_id,commit_hash), (repo_id,name) on branches), NOT NULL, CHECK (end_line >= start_line, additions/deletions >= 0), ENUM/CHECK for role/change_type/chunk_type, ON DELETE CASCADE, secondary indexes, FULLTEXT(code_chunks.content), views/procedures/triggers.

`code_chunks.embedding_ref` holds the Qdrant point ID (= chunk_id); NULL until embedded. The vector itself lives only in Qdrant.

### Approved additions (user approved 1–3 on 2026-11-02; apply in Phase 1 DDL)
1. `users.role` (e.g. admin/user). Brief §11 requires authentication with at least 2 roles; `repository_members.role` is per-repository and cannot express app-wide admin vs user.
2. `repositories.status` (+ `error_message`). Needed for the indexing-progress screen (Phase 4) and for recovering from failed imports; keeping it in memory would lose it on restart. Alternative: in-memory only.
3. `audit_log` table for triggers (Phase 5). Alternative needing no new table: triggers that maintain `repositories.last_synced_at` / `users.last_login`. Brief only needs 4 advanced concepts, so this is optional.

## API contract (JSON, prefix `/api`)

| Method & path | Purpose | Request | Response |
|---|---|---|---|
| GET `/health` | liveness + DB/Qdrant check | – | `{status, mysql, qdrant}` |
| POST `/api/repositories` | import public GitHub repo (async job) | `{git_url}` | `202 {repo_id}` |
| GET `/api/repositories` | list repos | – | `[{repo_id,name,primary_language,last_synced_at}]` (+ `status`) |
| GET `/api/repositories/{id}` | overview | – | repo row + counts |
| GET `/api/repositories/{id}/status` | indexing progress | – | `{status, stage, processed, total, error?}` |
| DELETE `/api/repositories/{id}` | delete repo (MySQL + Qdrant) | – | `204` |
| GET `/api/repositories/{id}/files` | file explorer | `?path=` | `[{file_id,file_path,language,line_count}]` |
| GET `/api/files/{file_id}` | file with functions/classes | – | file + symbols |
| POST `/api/search` | semantic search | `{query, repo_id?, language?, limit=10}` | `[{chunk_id,name,chunk_type,file_path,language,start_line,end_line,snippet,score}]` |
| GET `/api/repositories/{id}/analytics` | SQL analytics | – | language counts, symbol counts, largest files, commit/contributor stats, hot files |

Errors: `{error: {code, message}}`; internal details are logged server-side only.

## Key decisions

1. Indexing runs as a FastAPI `BackgroundTasks` job; status stored in `repositories.status` (+ in-memory progress). No Celery/Redis.
2. MySQL driver: `mysql-connector-python` with raw parameterized SQL (no ORM) — keeps SQL visible for the DBMS evaluation.
3. Chunking: one chunk per function/class (long ones split by line window); module-level remainder as `module` chunk. Embedding text = `path + name + signature + docstring + code`, truncated.
4. Security: GitHub URL regex allow-list (`https://github.com/<owner>/<repo>`), shallow clone (`depth=1` for code; bounded history fetch for commits), skip files > `MAX_FILE_SIZE_KB`, abort clone > `MAX_REPO_SIZE_MB`, resolve and verify every path stays inside the workspace.
5. Auth: brief §11 requires login + at least 2 roles. Password hashing (bcrypt/argon2) and token auth in backend; roles stored in approved `users.role`.
6. Point ID in Qdrant = `code_chunks.chunk_id`; `embedding_ref` stores it.

## Open items

- None. Decisions on `commits.branch_id` and additions 1–3 are made (all kept).
