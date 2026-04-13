from __future__ import annotations

import csv
import sqlite3
import time
from pathlib import Path

from poem_assoc.app import create_app
from poem_assoc.config import Config
from poem_assoc.constants import LEGACY_SEARCH_INDEX_VERSION, SEARCH_INDEX_VERSION
from poem_assoc.db import get_connection, init_db
from poem_assoc.index_metadata import get_index_state
from poem_assoc.locks import RebuildLock
from poem_assoc.rebuild import RebuildResult
from poem_assoc.search import SearchService
from poem_assoc.startup_upgrade import StartupUpgradeCoordinator, UpgradeStatus
from poem_assoc.synonyms import SynonymExpander
from tests.fixtures import make_embedding_blob


class StubEmbeddingService:
    def __init__(self, query_vectors: dict[str, list[float]]) -> None:
        first = next(iter(query_vectors.values()))
        self.dimension = len(first)
        self._query_vectors = query_vectors

    def encode_query(self, query: str):
        return self._query_vectors[query]


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


def _create_v1_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE poems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at)
            VALUES ('Legacy', 'Leaves were falling', 'Leaves were falling', NULL,
                    '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _regression_fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fixture_v2_regression.csv"


def _load_regression_rows() -> list[dict[str, str]]:
    with _regression_fixture_path().open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _wait_for_state(coordinator: StartupUpgradeCoordinator, state: str) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if coordinator.status().state == state:
            return
        time.sleep(0.01)
    raise AssertionError(f"Startup upgrade did not reach state {state!r}")


def _make_config(db_path: str) -> Config:
    return Config(
        db_path=db_path,
        secret_key="test-secret",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
        log_level="WARNING",
    )


def test_requires_rebuild_for_legacy_index_state(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    _create_v1_schema(temp_db_path)
    init_db(temp_db_path)

    coordinator = StartupUpgradeCoordinator(
        temp_db_path,
        embedding_service,
        lexical_processor,
        SearchService(temp_db_path, embedding_service, lexical_processor),
        RebuildLock(),
    )

    assert coordinator.requires_rebuild() is True


def test_requires_no_rebuild_for_current_index_state(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)

    coordinator = StartupUpgradeCoordinator(
        temp_db_path,
        embedding_service,
        lexical_processor,
        SearchService(temp_db_path, embedding_service, lexical_processor),
        RebuildLock(),
    )

    assert coordinator.requires_rebuild() is False


def test_failed_upgrade_status_disables_search_and_writes():
    status = UpgradeStatus.failed("boom")

    assert status.is_search_available() is False
    assert status.is_write_available() is False


def test_startup_upgrade_runs_against_legacy_database(temp_db_path, embedding_service):
    _create_v1_schema(temp_db_path)

    app = create_app(config_override=_make_config(temp_db_path), embedding_service=embedding_service)
    coordinator = app.extensions["startup_upgrade"]
    _wait_for_state(coordinator, "ready")

    conn = get_connection(temp_db_path)
    try:
        row = conn.execute(
            "SELECT lemmatized_search_text FROM poems WHERE title = 'Legacy'"
        ).fetchone()
        state = get_index_state(conn)
    finally:
        conn.close()

    assert row["lemmatized_search_text"]
    assert state.search_index_version == SEARCH_INDEX_VERSION
    assert state.last_successful_full_rebuild_at is not None


def test_noop_current_version_stays_ready(temp_db_path, embedding_service):
    init_db(temp_db_path)

    app = create_app(config_override=_make_config(temp_db_path), embedding_service=embedding_service)
    coordinator = app.extensions["startup_upgrade"]

    assert coordinator.status().state == "ready"
    assert coordinator.requires_rebuild() is False
    assert app.extensions["rebuild_lock"].is_rebuilding() is False


def test_failed_startup_upgrade_surfaces_error_until_retry(
    temp_db_path,
    embedding_service,
    monkeypatch,
):
    import poem_assoc.startup_upgrade as startup_upgrade_module

    _create_v1_schema(temp_db_path)
    monkeypatch.setattr(
        startup_upgrade_module,
        "run_rebuild",
        lambda conn, embedding_service, lexical_processor: RebuildResult(
            total=1,
            rebuilt=0,
            error="boom",
        ),
    )

    app = create_app(config_override=_make_config(temp_db_path), embedding_service=embedding_service)
    app.config["TESTING"] = True
    coordinator = app.extensions["startup_upgrade"]
    _wait_for_state(coordinator, "failed")

    conn = get_connection(temp_db_path)
    try:
        state = get_index_state(conn)
    finally:
        conn.close()

    assert state.search_index_version == LEGACY_SEARCH_INDEX_VERSION

    client = app.test_client()
    failed_index = client.get("/")
    assert failed_index.status_code == 200
    assert b"Search data upgrade failed." in failed_index.data
    assert b"boom" in failed_index.data

    failed_search = client.post("/search", data={"q": "leaves"})
    assert failed_search.status_code == 503

    client.post("/admin/login", data={"password": "test-pass"})
    client.get("/admin/")
    with client.session_transaction() as sess:
        token = sess["csrf_token"]

    retry = client.post("/admin/rebuild", data={"csrf_token": token})
    assert retry.status_code == 200
    assert b"Rebuild complete" in retry.data
    assert coordinator.status().state == "ready"

    recovered_search = client.post("/search", data={"q": "leaves"})
    assert recovered_search.status_code == 200


def test_upgrade_then_search_passes_full_v2_acceptance_path(
    temp_db_path,
    embedding_service,
    monkeypatch,
):
    _create_v1_schema(temp_db_path)
    rows = _load_regression_rows()
    conn = sqlite3.connect(temp_db_path)
    try:
        now = "2024-01-01T00:00:00+00:00"
        for row in rows:
            conn.execute(
                "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                (row["title"], row["text"], row["text"], now, now),
            )
        conn.commit()
    finally:
        conn.close()

    app = create_app(
        config_override=_make_config(temp_db_path),
        embedding_service=embedding_service,
    )
    coordinator = app.extensions["startup_upgrade"]
    _wait_for_state(coordinator, "ready")

    conn = get_connection(temp_db_path)
    try:
        lexical_rows = conn.execute(
            "SELECT title, lemmatized_search_text FROM poems ORDER BY id"
        ).fetchall()
        for index, row in enumerate(
            conn.execute("SELECT id FROM poems ORDER BY id").fetchall()
        ):
            conn.execute(
                "UPDATE poems SET embedding = ? WHERE id = ?",
                (make_embedding_blob(7, index=index), row["id"]),
            )
        conn.commit()
    finally:
        conn.close()

    assert all(row["lemmatized_search_text"] for row in lexical_rows)

    lexical_processor = app.extensions["lexical"]
    monkeypatch.setattr(
        lexical_processor,
        "_tag_tokens",
        lambda tokens: [
            (token, "JJ" if token == "quiet" else "NN") for token in tokens
        ],
    )
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [_FakeSynset(term, "sorrow")]
        if term == "grief" and pos == "n"
        else [],
    )

    deterministic_search = SearchService(
        temp_db_path,
        StubEmbeddingService(
            {"quiet grief": [0.05, 0.56, 0.55, 0.55, 0.53, 0.18, 0.19]}
        ),
        lexical_processor,
        synonym_expander=SynonymExpander(lexical_processor),
    )

    results = deterministic_search.search("quiet grief")

    assert len(results) == 5
    assert [result.title for result in results] == [
        "Lantern Vigil",
        "Ash Chorus",
        "Harbor Stone",
        "Cedar Rain",
        "Road Static",
    ]
    assert all(result.label in {"Strong", "Moderate", "Weak"} for result in results)
