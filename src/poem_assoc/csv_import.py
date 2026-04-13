from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, field
from typing import Callable

from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor
from .repository import (
    DuplicatePoemError,
    create_poem,
    find_by_title_and_cleaned_text,
)
from .text_cleaning import clean_poem_text

# Raise the default csv field size limit to handle large poem texts.
csv.field_size_limit(10 * 1024 * 1024)

_REQUIRED_HEADERS = {"title", "text"}


class CsvFormatError(Exception):
    """Raised when the CSV file has invalid format, headers, or encoding."""


@dataclass
class PlannedRow:
    title: str
    text: str
    cleaned_text: str


@dataclass
class ImportPlan:
    importable_rows: list[PlannedRow] = field(default_factory=list)
    duplicate_count: int = 0
    filename: str = ""


@dataclass
class ImportResult:
    imported: int = 0
    skipped_duplicates: int = 0
    cancelled: bool = False
    error: str | None = None


def plan(conn, csv_path_or_stream) -> ImportPlan:
    """Parse a strict CSV, classify rows as importable or duplicate."""
    if isinstance(csv_path_or_stream, (str, os.PathLike)):
        filename = os.path.basename(str(csv_path_or_stream))
        fh = open(csv_path_or_stream, "r", encoding="utf-8-sig", newline="")
        should_close = True
    else:
        filename = getattr(csv_path_or_stream, "name", "<stream>")
        fh = csv_path_or_stream
        should_close = False

    try:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            raise CsvFormatError("CSV file is empty or has no header row")

        header_set = set(reader.fieldnames)
        if header_set != _REQUIRED_HEADERS:
            raise CsvFormatError(
                f"CSV headers must be exactly {_REQUIRED_HEADERS}, "
                f"got {header_set}"
            )

        result = ImportPlan(filename=filename)
        seen_pairs: set[tuple[str, str]] = set()

        for row_num, row in enumerate(reader, start=2):
            text = row.get("text", "")
            title = row.get("title", "")

            if not text and not title:
                continue  # skip blank trailing lines

            title = title.strip()
            if not title:
                raise CsvFormatError(f"Row {row_num}: poem title is empty")

            cleaned = clean_poem_text(text)
            dedup_pair = (title, cleaned)

            if (
                dedup_pair in seen_pairs
                or find_by_title_and_cleaned_text(conn, title, cleaned) is not None
            ):
                result.duplicate_count += 1
            else:
                result.importable_rows.append(
                    PlannedRow(
                        title=title,
                        text=text,
                        cleaned_text=cleaned,
                    )
                )
                seen_pairs.add(dedup_pair)

        return result
    finally:
        if should_close:
            fh.close()


def execute(
    conn,
    import_plan: ImportPlan,
    embedding_service: EmbeddingService,
    lexical_processor: LexicalTextProcessor,
    cancel_flag: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ImportResult:
    """Walk the import plan row-by-row, inserting each poem."""
    result = ImportResult(skipped_duplicates=import_plan.duplicate_count)
    total = len(import_plan.importable_rows)

    for i, row in enumerate(import_plan.importable_rows):
        if cancel_flag is not None and cancel_flag():
            result.cancelled = True
            break

        try:
            create_poem(conn, row.title, row.text, embedding_service, lexical_processor)
            result.imported += 1
        except DuplicatePoemError:
            result.skipped_duplicates += 1
        except Exception as exc:
            result.error = str(exc)
            break

        if on_progress is not None:
            on_progress(i + 1, total)

    return result
