import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "grepright"

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "code_chunks"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    workspace_dir: str = "backend/workspace"
    max_repo_size_mb: int = 200
    max_file_size_kb: int = 500

    cors_origins: str = "http://localhost:3000"

    embed_batch_size: int = 64
    max_embed_chars: int = 2000          # embedding text is truncated to this many characters

    @field_validator("qdrant_url")
    @classmethod
    def _clean_qdrant_url(cls, v: str) -> str:
        # tolerate a doubled scheme such as "https:https://host" and trailing slashes
        v = v.strip()
        while True:
            m = re.match(r"^https?:(https?://.*)$", v)
            if not m:
                break
            v = m.group(1)
        return v.rstrip("/")


settings = Settings()
