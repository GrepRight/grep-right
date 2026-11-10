# CLAUDE.md

GrepRight — semantic code search (DBMS Level 3 project).

- At session start: read `AI.md`, check `git status`, continue from recorded phase. At session end: update `AI.md`.
- Architecture, schema, API: `docs/ARCHITECTURE.md`.
- **Never** run git add/commit/push/branch/merge or touch remotes; humans do that. Suggest commit messages instead.
- Work one phase at a time; wait for user approval before the next.
- Stack: Next.js+TS, FastAPI, MySQL (raw parameterized SQL), Qdrant Cloud, FastEmbed bge-small-en-v1.5 (384-d). No Docker/PyTorch/LLM.
- Secrets in `.env` only. Never execute imported repo code.
