-- GrepRight analytics queries (Phase 5). Reference copies; the API runs parameterized versions
-- (see backend/app/services/analytics.py). Replace @repo with a repo_id.

-- 1. Language breakdown with share of total lines (window function)
SELECT language, file_count, total_lines,
       ROUND(100 * total_lines / SUM(total_lines) OVER (), 1) AS pct_lines
FROM v_repo_language_stats WHERE repo_id = @repo ORDER BY total_lines DESC;

-- 2. Largest file per language (CTE + ROW_NUMBER)
WITH ranked AS (
  SELECT file_path, language, line_count,
         ROW_NUMBER() OVER (PARTITION BY language ORDER BY line_count DESC) AS rn
  FROM files WHERE repo_id = @repo)
SELECT file_path, language, line_count FROM ranked WHERE rn = 1;

-- 3. Files with more functions than the repository average (subquery)
SELECT file_path, function_count FROM v_file_summary
WHERE repo_id = @repo
  AND function_count > (SELECT AVG(function_count) FROM v_file_summary WHERE repo_id = @repo);

-- 4. Hot files
SELECT file_path, change_count FROM v_hot_files WHERE repo_id = @repo ORDER BY change_count DESC LIMIT 10;

-- 5. Cumulative commits over time (window function)
SELECT commit_date, commit_count, SUM(commit_count) OVER (ORDER BY commit_date) AS running_total
FROM v_commit_activity WHERE repo_id = @repo;

-- 6. Stored procedures / audit trail
CALL sp_repo_overview(@repo);
CALL sp_largest_files(@repo, 10);
SELECT * FROM audit_log ORDER BY log_id DESC LIMIT 20;
