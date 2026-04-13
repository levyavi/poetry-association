from __future__ import annotations

from poem_assoc.synonyms import SynonymExpander


class _FakeLemma:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class _FakeSynset:
    def __init__(self, *lemma_names: str) -> None:
        self._lemmas = [_FakeLemma(name) for name in lemma_names]

    def lemmas(self) -> list[_FakeLemma]:
        return list(self._lemmas)


def test_pos_filter_allows_nouns_and_adjectives_only(
    lexical_processor,
    monkeypatch,
):
    calls: list[tuple[str, str | None]] = []

    def fake_synsets(term: str, pos: str | None = None):
        calls.append((term, pos))
        return [_FakeSynset(term, "ally")]

    monkeypatch.setattr("poem_assoc.synonyms.wordnet.synsets", fake_synsets)
    expander = SynonymExpander(lexical_processor)

    assert expander.expand_term("grief", "NN") == ["ally"]
    assert expander.expand_term("quiet", "JJ") == ["ally"]
    assert expander.expand_term("run", "VB") == []
    assert expander.expand_term("swiftly", "RB") == []
    assert calls == [("grief", "n"), ("quiet", "a")]


def test_expand_term_uses_top_synset_only(lexical_processor, monkeypatch):
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [
            _FakeSynset(term, "sorrow"),
            _FakeSynset(term, "pain"),
        ],
    )
    expander = SynonymExpander(lexical_processor)

    assert expander.expand_term("grief", "NN") == ["sorrow"]


def test_expand_term_discards_multiword_and_original_term(
    lexical_processor,
    monkeypatch,
):
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [
            _FakeSynset(
                term,
                "visible_light",
                "the",
                "",
                "deep grief",
                "sorrow",
            )
        ],
    )
    expander = SynonymExpander(lexical_processor)

    assert expander.expand_term("grief", "NN") == ["sorrow"]


def test_expand_term_caps_at_five_after_normalization_and_dedup(
    lexical_processor,
    monkeypatch,
):
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [
            _FakeSynset(
                term,
                "leaves",
                "foliage",
                "foliage",
                "frond",
                "blade",
                "sprig",
                "shoot",
                "leafy",
            )
        ],
    )
    expander = SynonymExpander(lexical_processor)

    assert expander.expand_term("leaf", "NN") == [
        "foliage",
        "frond",
        "blade",
        "sprig",
        "shoot",
    ]


def test_no_usable_synonyms_returns_empty_list(lexical_processor, monkeypatch):
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [
            _FakeSynset(
                term,
                "the",
                "visible_light",
                "deep grief",
                term,
            )
        ],
    )
    expander = SynonymExpander(lexical_processor)

    assert expander.expand_term("grief", "NN") == []
