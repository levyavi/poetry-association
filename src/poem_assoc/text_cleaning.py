from __future__ import annotations

import re


def clean_poem_text(text: str) -> str:
    """Clean poem text for storage: normalize whitespace and line endings,
    preserve case, indentation, and meaningful line breaks."""
    if text is None:
        raise ValueError("text must not be None")

    # Normalize line endings: \r\n and \r → \n
    result = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip leading/trailing whitespace from the whole text
    result = result.strip()

    # Strip trailing whitespace from each line
    result = "\n".join(line.rstrip() for line in result.split("\n"))

    # Collapse 3+ consecutive blank lines to 2 (i.e. at most one empty line gap)
    result = re.sub(r"\n{4,}", "\n\n\n", result)

    return result


def compute_dedup_key(cleaned_text: str) -> str:
    """Produce the canonical form for duplicate detection.

    Collapses all internal whitespace runs (spaces, tabs, newlines) to single
    spaces. Case is preserved per design doc §6.3.3.
    """
    return " ".join(cleaned_text.split())


def clean_query(query: str) -> str:
    """Normalize a search query: trim, lowercase, collapse whitespace,
    normalize smart quotes to ASCII."""
    if not query or not query.strip():
        return ""

    result = query.strip().lower()

    # Normalize smart quotes to ASCII
    result = result.replace("\u2018", "'").replace("\u2019", "'")
    result = result.replace("\u201c", '"').replace("\u201d", '"')

    # Collapse internal whitespace
    result = " ".join(result.split())

    return result
