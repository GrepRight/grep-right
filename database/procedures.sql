-- GrepRight stored procedures (Phase 5). Statements are separated by a line containing only $$.

DROP PROCEDURE IF EXISTS sp_repo_overview
$$
CREATE PROCEDURE sp_repo_overview(IN p_repo_id INT UNSIGNED)
BEGIN
    SELECT
        (SELECT COUNT(*) FROM files WHERE repo_id = p_repo_id)                           AS files,
        (SELECT COALESCE(SUM(function_count), 0) FROM v_file_summary WHERE repo_id = p_repo_id) AS functions,
        (SELECT COALESCE(SUM(class_count), 0)    FROM v_file_summary WHERE repo_id = p_repo_id) AS classes,
        (SELECT COALESCE(SUM(chunk_count), 0)    FROM v_file_summary WHERE repo_id = p_repo_id) AS chunks,
        (SELECT COUNT(*) FROM commits WHERE repo_id = p_repo_id)                         AS commits,
        (SELECT COALESCE(SUM(additions), 0) FROM commits WHERE repo_id = p_repo_id)      AS additions,
        (SELECT COALESCE(SUM(deletions), 0) FROM commits WHERE repo_id = p_repo_id)      AS deletions,
        (SELECT MIN(committed_at) FROM commits WHERE repo_id = p_repo_id)                AS first_commit,
        (SELECT MAX(committed_at) FROM commits WHERE repo_id = p_repo_id)                AS last_commit;
END
$$
DROP PROCEDURE IF EXISTS sp_largest_files
$$
CREATE PROCEDURE sp_largest_files(IN p_repo_id INT UNSIGNED, IN p_limit INT)
BEGIN
    SELECT file_id, file_path, language, line_count, function_count, class_count
    FROM v_file_summary
    WHERE repo_id = p_repo_id
    ORDER BY line_count DESC, file_id
    LIMIT p_limit;
END
$$
