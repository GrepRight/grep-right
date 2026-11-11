-- GrepRight triggers (Phase 5): write an audit trail into audit_log.
-- Statements are separated by a line containing only $$.

DROP TRIGGER IF EXISTS trg_repositories_ai
$$
CREATE TRIGGER trg_repositories_ai AFTER INSERT ON repositories
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, details)
    VALUES ('repositories', 'INSERT', NEW.repo_id, CONCAT('imported ', NEW.git_url));
END
$$
DROP TRIGGER IF EXISTS trg_repositories_au
$$
CREATE TRIGGER trg_repositories_au AFTER UPDATE ON repositories
FOR EACH ROW
BEGIN
    IF NOT (OLD.status <=> NEW.status) THEN
        INSERT INTO audit_log (table_name, action, record_id, details)
        VALUES ('repositories', 'UPDATE', NEW.repo_id, CONCAT('status ', OLD.status, ' -> ', NEW.status));
    END IF;
END
$$
DROP TRIGGER IF EXISTS trg_repositories_ad
$$
CREATE TRIGGER trg_repositories_ad AFTER DELETE ON repositories
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, details)
    VALUES ('repositories', 'DELETE', OLD.repo_id, CONCAT('deleted ', OLD.git_url));
END
$$
DROP TRIGGER IF EXISTS trg_users_au
$$
CREATE TRIGGER trg_users_au AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    IF NOT (OLD.role <=> NEW.role) THEN
        INSERT INTO audit_log (table_name, action, record_id, details)
        VALUES ('users', 'UPDATE', NEW.user_id, CONCAT('role ', OLD.role, ' -> ', NEW.role));
    END IF;
END
$$
-- Validation: a commit cannot be dated in the future.
DROP TRIGGER IF EXISTS trg_commits_bi
$$
CREATE TRIGGER trg_commits_bi BEFORE INSERT ON commits
FOR EACH ROW
BEGIN
    IF NEW.committed_at IS NOT NULL AND NEW.committed_at > (NOW() + INTERVAL 1 DAY) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'committed_at is in the future';
    END IF;
END
$$
