from __future__ import annotations

from pathlib import Path

import pytest

from poem_assoc.config import Config
from poem_assoc.lexical import LexicalResourceError, LexicalTextProcessor


def test_lexical_text_processor_builds_deterministic_search_text(lexical_processor):
    text = lexical_processor.build_search_text("Cats", "Running dogs")
    assert text == "cat run dog"
    assert lexical_processor.build_search_text("Cats", "Running dogs") == text


def test_lexical_text_processor_uses_title_and_body(lexical_processor):
    text = lexical_processor.build_search_text("Owls", "Foxes howled nearby")
    tokens = set(text.split())
    assert "owl" in tokens
    assert "fox" in tokens
    assert "howl" in tokens


def test_validate_resources_fails_when_required_assets_missing(tmp_path):
    processor = LexicalTextProcessor(str(tmp_path))
    with pytest.raises(LexicalResourceError, match="Missing required local NLTK resources"):
        processor.validate_resources()


def test_packaged_nltk_resources_exist_under_package_path():
    cfg = Config(
        db_path="./unused.db",
        secret_key="test-secret",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
    )
    root = Path(cfg.nltk_data_path)
    assert (root / "corpora" / "wordnet.zip").is_file()
    assert (root / "taggers" / "averaged_perceptron_tagger_eng.zip").is_file()
