from __future__ import annotations

import os
import re
import unicodedata

import nltk
from nltk.stem import WordNetLemmatizer

from .text_cleaning import clean_poem_text

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
_RESOURCE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "wordnet": ("corpora/wordnet", "corpora/wordnet.zip"),
    "averaged_perceptron_tagger_eng": (
        "taggers/averaged_perceptron_tagger_eng",
        "taggers/averaged_perceptron_tagger_eng.zip",
    ),
}
_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": " ",
        "\u2014": " ",
        "\u2026": " ",
    }
)


class LexicalResourceError(RuntimeError):
    """Raised when the local NLTK resource bundle is missing or incomplete."""


class LexicalTextProcessor:
    """Build deterministic lemmatized search text using local bundled NLTK data."""

    def __init__(self, nltk_data_path: str) -> None:
        self._nltk_data_path = os.path.abspath(nltk_data_path)
        self._lemmatizer = WordNetLemmatizer()
        self._validated = False
        self._register_data_path()

    @property
    def nltk_data_path(self) -> str:
        return self._nltk_data_path

    def validate_resources(self) -> None:
        """Verify the configured local NLTK data path contains required assets."""
        self._register_data_path()

        if not os.path.isdir(self._nltk_data_path):
            raise LexicalResourceError(
                f"Configured NLTK data path does not exist: {self._nltk_data_path}"
            )

        missing = [
            resource_name
            for resource_name, candidates in _RESOURCE_CANDIDATES.items()
            if not any(self._resource_exists(candidate) for candidate in candidates)
        ]
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise LexicalResourceError(
                f"Missing required local NLTK resources at {self._nltk_data_path}: "
                f"{missing_list}"
            )

        self._validated = True

    def build_search_text(self, title: str, text: str) -> str:
        """Return the normalized lemmatized lexical index text for a poem."""
        if text is None:
            raise ValueError("text must not be None")
        if not self._validated:
            self.validate_resources()

        combined = self._combine_title_and_body(title, text)
        tokens = self._tokenize(combined)
        if not tokens:
            raise ValueError("Poem does not contain any searchable lexical tokens")

        tagged_tokens = nltk.pos_tag(tokens, lang="eng")
        lemmas = [self._lemmatize(token, pos_tag) for token, pos_tag in tagged_tokens]
        search_text = " ".join(lemmas).strip()
        if not search_text:
            raise ValueError("Poem does not contain any searchable lexical tokens")
        return search_text

    def _register_data_path(self) -> None:
        normalized_target = os.path.normcase(self._nltk_data_path)
        existing = {os.path.normcase(os.path.abspath(path)) for path in nltk.data.path}
        if normalized_target not in existing:
            nltk.data.path.insert(0, self._nltk_data_path)

    def _resource_exists(self, resource_id: str) -> bool:
        resource_path = os.path.join(
            self._nltk_data_path, *resource_id.split("/")
        )
        return os.path.exists(resource_path)

    def _combine_title_and_body(self, title: str, text: str) -> str:
        parts = []
        if title and title.strip():
            parts.append(title.strip())
        cleaned_body = clean_poem_text(text)
        if cleaned_body:
            parts.append(cleaned_body)
        return "\n".join(parts)

    def _tokenize(self, value: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = normalized.translate(_PUNCT_TRANSLATION).lower()
        return _WORD_RE.findall(normalized)

    def _lemmatize(self, token: str, pos_tag: str) -> str:
        wn_pos = self._to_wordnet_pos(pos_tag)
        if wn_pos is None:
            return self._lemmatizer.lemmatize(token)
        return self._lemmatizer.lemmatize(token, wn_pos)

    def _to_wordnet_pos(self, pos_tag: str) -> str | None:
        if pos_tag.startswith("J"):
            return "a"
        if pos_tag.startswith("N"):
            return "n"
        if pos_tag.startswith("R"):
            return "r"
        if pos_tag.startswith("V"):
            return "v"
        return None
