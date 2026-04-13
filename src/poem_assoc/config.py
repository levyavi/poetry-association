from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from importlib import resources


def _read_bool_from_environment(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


@dataclass
class Config:
    db_path: str
    secret_key: str
    admin_password: str
    model_name: str
    model_path: str | None
    nltk_data_path: str = ""
    import_temp_dir: str = ""
    enable_synonym_expansion: bool = True

    def __post_init__(self) -> None:
        if not self.import_temp_dir:
            self.import_temp_dir = os.path.join(
                os.path.dirname(self.db_path) or ".", "_import_tmp"
            )
        if not self.nltk_data_path:
            self.nltk_data_path = os.fspath(
                resources.files("poem_assoc").joinpath("resources", "nltk_data")
            )
        self.nltk_data_path = os.path.abspath(self.nltk_data_path)

    @classmethod
    def from_environment(cls) -> "Config":
        return cls(
            db_path=os.environ.get("POEM_DB_PATH", "./poem_assoc.db"),
            secret_key=os.environ.get("POEM_SECRET_KEY", secrets.token_hex(32)),
            admin_password=os.environ.get("POEM_ADMIN_PASSWORD", ""),
            model_name=os.environ.get("POEM_MODEL_NAME", "all-MiniLM-L6-v2"),
            model_path=os.environ.get("POEM_MODEL_PATH") or None,
            nltk_data_path=os.environ.get("POEM_NLTK_DATA_PATH", ""),
            import_temp_dir=os.environ.get("POEM_IMPORT_TEMP_DIR", ""),
            enable_synonym_expansion=_read_bool_from_environment(
                "ENABLE_SYNONYM_EXPANSION", True
            ),
        )
