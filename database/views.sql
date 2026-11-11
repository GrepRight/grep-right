-- GrepRight views (Phase 5). Idempotent: CREATE OR REPLACE.

-- Files / lines per language per repository.
CREATE OR REPLACE VIEW v_repo_language_stats AS
SELECT f.repo_id,
       COALESCE(f.language, 'unknown') AS language,
       COUNT(*)                        AS file_count,
       SUM(f.line_count)               AS total_lines,
       SUM(f.size_bytes)               AS total_bytes
FROM files f
GROUP BY f.repo_id, COALESCE(f.language, 'unknown');

-- One row per file with its symbol / chunk counts.
CREATE OR REPLACE VIEW v_file_summary AS
SELECT f.file_id, f.repo_id, f.file_path, f.language, f.line_count, f.size_bytes,
       (SELECT COUNT(*) FROM functions fn WHERE fn.file_id = f.file_id) AS function_count,
       (SELECT COUNT(*) FROM classes   c  WHERE c.file_id  = f.file_id) AS class_count,
       (SELECT COUNT(*) FROM code_chunks ch WHERE ch.file_id = f.file_id) AS chunk_count
FROM files f;

-- Most frequently changed files (from commit history).
CREATE OR REPLACE VIEW v_hot_files AS
SELECT f.repo_id, f.file_id, f.file_path,
       COUNT(*)            AS change_count,
       SUM(cf.additions)   AS total_additions,
       SUM(cf.deletions)   AS total_deletions
FROM commit_files cf
JOIN files f ON f.file_id = cf.file_id
GROUP BY f.repo_id, f.file_id, f.file_path;

-- Per-day commit activity.
CREATE OR REPLACE VIEW v_commit_activity AS
SELECT c.repo_id,
       DATE(c.committed_at) AS commit_date,
       COUNT(*)             AS commit_count,
       SUM(c.additions)     AS additions,
       SUM(c.deletions)     AS deletions
FROM commits c
WHERE c.committed_at IS NOT NULL
GROUP BY c.repo_id, DATE(c.committed_at);
