from __future__ import annotations

import sys

from .config import Config
from .csv_import import CsvFormatError, execute, plan
from .db import get_connection, init_db
from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor


def import_csv(argv: list[str]) -> int:
    """CLI entry point for ``python -m poem_assoc import-csv <path>``."""
    if not argv:
        print("Usage: python -m poem_assoc import-csv <csv-path>", file=sys.stderr)
        return 1

    csv_path = argv[0]

    try:
        with open(csv_path, "r", encoding="utf-8-sig"):
            pass
    except FileNotFoundError:
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: cannot read file: {exc}", file=sys.stderr)
        return 1

    cfg = Config.from_environment()
    lexical_processor = LexicalTextProcessor(cfg.nltk_data_path)
    try:
        lexical_processor.validate_resources()
    except Exception as exc:
        print(f"Error: failed to validate local NLP resources: {exc}", file=sys.stderr)
        return 1

    init_db(cfg.db_path)

    print("Loading embedding model...", flush=True)
    try:
        model_ref = cfg.model_path if cfg.model_path else cfg.model_name
        embedding_service = EmbeddingService(model_ref)
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

    result = execute(conn, import_plan, embedding_service, lexical_processor)
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
