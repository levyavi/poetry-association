from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


@dataclass
class Config:
    db_path: str
    secret_key: str
    admin_password: str

    @classmethod
    def from_environment(cls) -> "Config":
        return cls(
            db_path=os.environ.get("POEM_DB_PATH", "./poem_assoc.db"),
            secret_key=os.environ.get("POEM_SECRET_KEY", secrets.token_hex(32)),
            admin_password=os.environ.get("POEM_ADMIN_PASSWORD", ""),
        )
