from __future__ import annotations

# Relevance label thresholds (design doc §6.1.3).
# Adjust here only — all label logic flows through label_for().
STRONG_THRESHOLD: float = 0.45
MODERATE_THRESHOLD: float = 0.30
SCHEMA_VERSION: str = "2"
SEARCH_INDEX_VERSION: str = "v2"
LEGACY_SEARCH_INDEX_VERSION: str = "v1"


def label_for(score: float) -> str:
    """Map a cosine similarity score to a human-readable relevance label."""
    if score >= STRONG_THRESHOLD:
        return "Strong"
    if score >= MODERATE_THRESHOLD:
        return "Moderate"
    return "Weak"
