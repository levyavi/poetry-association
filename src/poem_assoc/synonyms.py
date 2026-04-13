from __future__ import annotations

from nltk.corpus import wordnet

from .lexical import LexicalTextProcessor, TaggedQueryTerm

_MAX_SYNONYMS_PER_TERM = 5


class SynonymExpander:
    """Resolve conservative query-time synonym sets from local WordNet."""

    def __init__(self, lexical_processor: LexicalTextProcessor) -> None:
        self._lexical_processor = lexical_processor

    def expand_term(self, term: str, pos_tag: str | None) -> list[str]:
        """Return normalized single-word synonyms from the top synset only."""
        wordnet_pos = self._to_wordnet_pos(pos_tag)
        if wordnet_pos is None:
            return []

        try:
            synsets = wordnet.synsets(term, pos=wordnet_pos)
        except Exception:
            return []

        if not synsets:
            return []

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
        return synonyms

    def expand_terms(
        self,
        tagged_terms: list[TaggedQueryTerm],
    ) -> dict[str, list[str]]:
        """Return per-term synonym expansions for eligible query words only."""
        expansions: dict[str, list[str]] = {}
        for tagged_term in tagged_terms:
            synonyms = self.expand_term(tagged_term.term, tagged_term.pos_tag)
            if synonyms:
                expansions[tagged_term.term] = synonyms
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
