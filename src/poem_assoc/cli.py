from __future__ import annotations

import sys

from .config import Config
from .csv_import import CsvFormatError, execute, plan
from .db import get_connection, init_db
from .embedding import EmbeddingService


def import_csv(argv: list[str]) -> int:
    """CLI entry point for ``python -m poem_assoc import-csv <path>``.

    Returns a process exit code (0 on success, 1 on failure).
    """
    if not argv:
        print("Usage: python -m poem_assoc import-csv <csv-path>", file=sys.stderr)
        return 1

    csv_path = argv[0]

    try:
        with open(csv_path, "r", encoding="utf-8-sig"):
            pass  # validate file exists and is readable
    except FileNotFoundError:
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: cannot read file: {exc}", file=sys.stderr)
        return 1

    cfg = Config.from_environment()
    init_db(cfg.db_path)

    print("Loading embedding model...", flush=True)
    try:
        embedding_service = EmbeddingService(cfg.model_name)
    except Exception as exc:
        print(f"Error: failed to load embedding model: {exc}", file=sys.stderr)
        return 1
    print(f"Embedding model ready ({cfg.model_name})", flush=True)

    conn = get_connection(cfg.db_path)
    try:
        import_plan = plan(conn, csv_path)
    except CsvFormatError as exc:
        print(f"CSV format error: {exc}", file=sys.stderr)
        conn.close()
        return 1

    result = execute(conn, import_plan, embedding_service)
    conn.close()

    if result.error:
        print(
            f"Import stopped with error after {result.imported} poems: {result.error}",
            file=sys.stderr,
        )
        return 1

    print(
        f"Imported {result.imported} poems, "
        f"skipped {result.skipped_duplicates} duplicates"
    )
    return 0
