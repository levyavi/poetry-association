from __future__ import annotations

# Search scoring constants (V1 + V2 design docs).
SEARCH_RESULT_LIMIT: int = 5
SEMANTIC_WEIGHT: float = 0.8
LEXICAL_WEIGHT: float = 0.2
SEMANTIC_FLOOR: float = 0.20
EXACT_LEXICAL_MATCH_VALUE: float = 1.0
SYNONYM_LEXICAL_MATCH_VALUE: float = 0.7

# Relevance label thresholds.
# Adjust here only — all label logic flows through label_for().
STRONG_THRESHOLD: float = 0.45
MODERATE_THRESHOLD: float = 0.30
SCHEMA_VERSION: str = "2"
SEARCH_INDEX_VERSION: str = "v2"
LEGACY_SEARCH_INDEX_VERSION: str = "v1"


def label_for(score: float) -> str:
    """Map a final search score to a human-readable relevance label."""
    if score >= STRONG_THRESHOLD:
        return "Strong"
    if score >= MODERATE_THRESHOLD:
        return "Moderate"
    return "Weak"
