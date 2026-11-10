-- GrepRight schema (Phase 1). MySQL 8.0, InnoDB, utf8mb4.
-- Mirrors the ER diagram / relational schema + approved additions
-- (users.role, repositories.status/error_message, commits.branch_id, audit_log).
-- Idempotent: safe to re-run (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS users (
    user_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username       VARCHAR(50)  NOT NULL,
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('admin','user') NOT NULL DEFAULT 'user',
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login     TIMESTAMP    NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email),
    CONSTRAINT chk_users_username CHECK (CHAR_LENGTH(username) >= 3),
    CONSTRAINT chk_users_email CHECK (email LIKE '%_@_%.__%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repositories (
    repo_id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_id         INT UNSIGNED NOT NULL,
    name             VARCHAR(255) NOT NULL,
    description      TEXT         NULL,
    git_url          VARCHAR(500) NOT NULL,
    default_branch   VARCHAR(255) NULL,
    primary_language VARCHAR(50)  NULL,
    status           ENUM('pending','cloning','indexing','ready','failed') NOT NULL DEFAULT 'pending',
    error_message    TEXT         NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_synced_at   TIMESTAMP    NULL,
    PRIMARY KEY (repo_id),
    UNIQUE KEY uq_repositories_git_url (git_url),
    KEY idx_repositories_owner (owner_id),
    CONSTRAINT fk_repositories_owner FOREIGN KEY (owner_id)
        REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_repositories_git_url CHECK (git_url LIKE 'https://github.com/%/%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS repository_members (
    user_id   INT UNSIGNED NOT NULL,
    repo_id   INT UNSIGNED NOT NULL,
    role      ENUM('owner','maintainer','viewer') NOT NULL DEFAULT 'viewer',
    joined_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, repo_id),
    KEY idx_members_repo (repo_id),
    CONSTRAINT fk_members_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_members_repo FOREIGN KEY (repo_id)
        REFERENCES repositories (repo_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS branches (
    branch_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    repo_id          INT UNSIGNED NOT NULL,
    name             VARCHAR(255) NOT NULL,
    head_commit_hash CHAR(40)     NULL,
    is_default       BOOLEAN      NOT NULL DEFAULT FALSE,
    PRIMARY KEY (branch_id),
    UNIQUE KEY uq_branches_repo_name (repo_id, name),
    CONSTRAINT fk_branches_repo FOREIGN KEY (repo_id)
        REFERENCES repositories (repo_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS commits (
    commit_id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    commit_hash  CHAR(40)     NOT NULL,
    repo_id      INT UNSIGNED NOT NULL,
    branch_id    INT UNSIGNED NULL,
    author_id    INT UNSIGNED NULL,
    message      TEXT         NULL,
    committed_at TIMESTAMP    NULL,
    additions    INT UNSIGNED NOT NULL DEFAULT 0,
    deletions    INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (commit_id),
    UNIQUE KEY uq_commits_repo_hash (repo_id, commit_hash),
    KEY idx_commits_branch (branch_id),
    KEY idx_commits_author (author_id),
    CONSTRAINT fk_commits_repo FOREIGN KEY (repo_id)
        REFERENCES repositories (repo_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_commits_branch FOREIGN KEY (branch_id)
        REFERENCES branches (branch_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_commits_author FOREIGN KEY (author_id)
        REFERENCES users (user_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS files (
    file_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    repo_id       INT UNSIGNED NOT NULL,
    file_path     VARCHAR(700) NOT NULL,
    language      VARCHAR(50)  NULL,
    size_bytes    INT UNSIGNED NOT NULL DEFAULT 0,
    line_count    INT UNSIGNED NOT NULL DEFAULT 0,
    last_modified TIMESTAMP    NULL,
    PRIMARY KEY (file_id),
    -- file_path prefix index keeps the key within InnoDB's 3072-byte limit (utf8mb4)
    UNIQUE KEY uq_files_repo_path (repo_id, file_path(500)),
    KEY idx_files_language (language),
    CONSTRAINT fk_files_repo FOREIGN KEY (repo_id)
        REFERENCES repositories (repo_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS commit_files (
    commit_id   BIGINT UNSIGNED NOT NULL,
    file_id     INT UNSIGNED    NOT NULL,
    change_type ENUM('added','modified','deleted','renamed') NOT NULL,
    additions   INT UNSIGNED NOT NULL DEFAULT 0,
    deletions   INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (commit_id, file_id),
    KEY idx_commit_files_file (file_id),
    CONSTRAINT fk_cf_commit FOREIGN KEY (commit_id)
        REFERENCES commits (commit_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cf_file FOREIGN KEY (file_id)
        REFERENCES files (file_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS functions (
    func_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    file_id    INT UNSIGNED NOT NULL,
    name       VARCHAR(255) NOT NULL,
    signature  TEXT         NULL,
    start_line INT UNSIGNED NOT NULL,
    end_line   INT UNSIGNED NOT NULL,
    docstring  TEXT         NULL,
    PRIMARY KEY (func_id),
    KEY idx_functions_file (file_id),
    KEY idx_functions_name (name),
    CONSTRAINT fk_functions_file FOREIGN KEY (file_id)
        REFERENCES files (file_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_functions_lines CHECK (start_line >= 1 AND end_line >= start_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS classes (
    class_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    file_id    INT UNSIGNED NOT NULL,
    name       VARCHAR(255) NOT NULL,
    start_line INT UNSIGNED NOT NULL,
    end_line   INT UNSIGNED NOT NULL,
    docstring  TEXT         NULL,
    PRIMARY KEY (class_id),
    KEY idx_classes_file (file_id),
    KEY idx_classes_name (name),
    CONSTRAINT fk_classes_file FOREIGN KEY (file_id)
        REFERENCES files (file_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_classes_lines CHECK (start_line >= 1 AND end_line >= start_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS code_chunks (
    chunk_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,  -- also the Qdrant point ID
    file_id       INT UNSIGNED    NOT NULL,
    chunk_type    ENUM('function','class','module') NOT NULL,
    content       MEDIUMTEXT      NOT NULL,
    start_line    INT UNSIGNED    NOT NULL,
    end_line      INT UNSIGNED    NOT NULL,
    embedding_ref BIGINT UNSIGNED NULL,                     -- Qdrant point ID; NULL until embedded
    PRIMARY KEY (chunk_id),
    KEY idx_chunks_file (file_id),
    KEY idx_chunks_type (chunk_type),
    FULLTEXT KEY ft_chunks_content (content),
    CONSTRAINT fk_chunks_file FOREIGN KEY (file_id)
        REFERENCES files (file_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_chunks_lines CHECK (start_line >= 1 AND end_line >= start_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Written by triggers in Phase 5; no FKs so history survives deletes.
CREATE TABLE IF NOT EXISTS audit_log (
    log_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    table_name VARCHAR(64)  NOT NULL,
    action     ENUM('INSERT','UPDATE','DELETE') NOT NULL,
    record_id  BIGINT UNSIGNED NULL,
    details    TEXT         NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    KEY idx_audit_table_time (table_name, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
