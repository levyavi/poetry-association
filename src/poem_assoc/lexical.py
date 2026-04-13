from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

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
_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "just",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


class LexicalResourceError(RuntimeError):
    """Raised when the local NLTK resource bundle is missing or incomplete."""


@dataclass(frozen=True)
class TaggedQueryTerm:
    """Normalized query term plus the POS tag used for synonym eligibility."""

    term: str
    pos_tag: str | None


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
        lemmas = self._lemmatize_tokens(tokens)
        search_text = " ".join(lemmas).strip()
        if not search_text:
            raise ValueError("Poem does not contain any searchable lexical tokens")
        return search_text

    def build_query_terms(self, query: str) -> list[str]:
        """Return normalized lemmatized non-stopword query terms for lexical scoring."""
        return [tagged.term for tagged in self.build_tagged_query_terms(query)]

    def build_tagged_query_terms(self, query: str) -> list[TaggedQueryTerm]:
        """Return normalized query terms annotated with the POS tagger output."""
        if not query:
            return []
        if not self._validated:
            self.validate_resources()

        try:
            tokens = [
                token for token in self._tokenize(query) if token not in _STOPWORDS
            ]
        except Exception:
            return []

        if not tokens:
            return []

        tagged_terms: list[TaggedQueryTerm] = []
        seen: set[str] = set()
        for token, pos_tag in self._tag_tokens(tokens):
            lemma = self.normalize_term(token, pos_tag=pos_tag)
            if not lemma or lemma in seen:
                continue
            seen.add(lemma)
            tagged_terms.append(TaggedQueryTerm(term=lemma, pos_tag=pos_tag))
        return tagged_terms

    def normalize_term(self, value: str, pos_tag: str | None = None) -> str | None:
        """Normalize one candidate term into the shared lemmatized lexical space."""
        tokens = self._tokenize(value)
        if len(tokens) != 1:
            return None

        token = tokens[0]
        if token in _STOPWORDS:
            return None

        lemma = self._lemmatize(token, pos_tag)
        return lemma or None

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

    def _lemmatize_tokens(self, tokens: list[str]) -> list[str]:
        if not tokens:
            raise ValueError("Input does not contain any searchable lexical tokens")

        tagged_tokens = self._tag_tokens(tokens)
        return [self._lemmatize(token, pos_tag) for token, pos_tag in tagged_tokens]

    def _tag_tokens(self, tokens: list[str]) -> list[tuple[str, str | None]]:
        try:
            return list(nltk.pos_tag(tokens, lang="eng"))
        except Exception:
            return [(token, None) for token in tokens]

    def _lemmatize(self, token: str, pos_tag: str | None) -> str:
        wn_pos = self._to_wordnet_pos(pos_tag)
        if wn_pos is None:
            return self._lemmatizer.lemmatize(token)
        return self._lemmatizer.lemmatize(token, wn_pos)

    def _to_wordnet_pos(self, pos_tag: str | None) -> str | None:
        if pos_tag is None:
            return None
        if pos_tag in {"a", "n", "r", "v"}:
            return pos_tag
        if pos_tag == "s":
            return "a"
        if pos_tag.startswith("J"):
            return "a"
        if pos_tag.startswith("N"):
            return "n"
        if pos_tag.startswith("R"):
            return "r"
        if pos_tag.startswith("V"):
            return "v"
        return None
