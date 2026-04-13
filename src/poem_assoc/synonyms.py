from __future__ import annotations

from dataclasses import dataclass

from nltk.corpus import wordnet

from .lexical import LexicalTextProcessor, TaggedQueryTerm

_MAX_SYNONYMS_PER_TERM = 5


@dataclass(frozen=True)
class SynonymExpansion:
    term: str
    pos_tag: str | None
    wordnet_pos: str | None
    synonyms: tuple[str, ...]
    cache_hit: bool | None


@dataclass
class _CacheEntry:
    wordnet_pos: str
    synonyms: tuple[str, ...]


class SynonymExpander:
    """Resolve conservative query-time synonym sets from local WordNet."""

    def __init__(self, lexical_processor: LexicalTextProcessor) -> None:
        self._lexical_processor = lexical_processor
        self._cache: dict[str, _CacheEntry] = {}

    def expand_term(self, term: str, pos_tag: str | None) -> SynonymExpansion:
        """Return normalized single-word synonyms from the top synset only."""
        wordnet_pos = self._to_wordnet_pos(pos_tag)
        if wordnet_pos is None:
            return SynonymExpansion(term, pos_tag, None, (), None)

        cached = self._cache.get(term)
        if (
            isinstance(cached, _CacheEntry)
            and cached.wordnet_pos == wordnet_pos
            and isinstance(cached.synonyms, tuple)
        ):
            return SynonymExpansion(
                term,
                pos_tag,
                cached.wordnet_pos,
                cached.synonyms,
                True,
            )

        if term in self._cache:
            self._cache.pop(term, None)

        try:
            synsets = wordnet.synsets(term, pos=wordnet_pos)
        except Exception:
            return SynonymExpansion(term, pos_tag, wordnet_pos, (), False)

        if not synsets:
            self._cache[term] = _CacheEntry(wordnet_pos=wordnet_pos, synonyms=())
            return SynonymExpansion(term, pos_tag, wordnet_pos, (), False)

        synonyms: list[str] = []
        seen = {term}
        for lemma in synsets[0].lemmas():
            normalized = self._lexical_processor.normalize_term(
                lemma.name(),
                pos_tag=wordnet_pos,
            )
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            synonyms.append(normalized)
            if len(synonyms) >= _MAX_SYNONYMS_PER_TERM:
                break

        cached_entry = _CacheEntry(wordnet_pos=wordnet_pos, synonyms=tuple(synonyms))
        self._cache[term] = cached_entry
        return SynonymExpansion(
            term,
            pos_tag,
            wordnet_pos,
            cached_entry.synonyms,
            False,
        )

    def expand_terms(
        self,
        tagged_terms: list[TaggedQueryTerm],
    ) -> dict[str, SynonymExpansion]:
        """Return per-term synonym expansions for eligible query words only."""
        expansions: dict[str, SynonymExpansion] = {}
        for tagged_term in tagged_terms:
            expansion = self.expand_term(tagged_term.term, tagged_term.pos_tag)
            expansions[tagged_term.term] = expansion
        return expansions

    def _to_wordnet_pos(self, pos_tag: str | None) -> str | None:
        if pos_tag is None:
            return None
        if pos_tag in {"n", "a"}:
            return pos_tag
        if pos_tag == "s":
            return "a"
        if pos_tag.startswith("N"):
            return "n"
        if pos_tag.startswith("J"):
            return "a"
        return None
