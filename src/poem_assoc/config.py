from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


@dataclass
class Config:
    db_path: str
    secret_key: str
    admin_password: str
    model_name: str
    model_path: str | None
    import_temp_dir: str = ""

    def __post_init__(self) -> None:
        if not self.import_temp_dir:
            self.import_temp_dir = os.path.join(
                os.path.dirname(self.db_path) or ".", "_import_tmp"
            )

    @classmethod
    def from_environment(cls) -> "Config":
        return cls(
            db_path=os.environ.get("POEM_DB_PATH", "./poem_assoc.db"),
            secret_key=os.environ.get("POEM_SECRET_KEY", secrets.token_hex(32)),
            admin_password=os.environ.get("POEM_ADMIN_PASSWORD", ""),
            model_name=os.environ.get("POEM_MODEL_NAME", "all-MiniLM-L6-v2"),
            model_path=os.environ.get("POEM_MODEL_PATH") or None,
            import_temp_dir=os.environ.get("POEM_IMPORT_TEMP_DIR", ""),
        )
