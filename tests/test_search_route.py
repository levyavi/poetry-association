"""Tests for the public search route (POST /search)."""

from __future__ import annotations

from poem_assoc.db import get_connection
from poem_assoc.repository import create_poem
from poem_assoc.startup_upgrade import UpgradeStatus
from tests.fixtures import insert_poem_raw, make_embedding_blob


def test_get_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_search_route_empty_query_no_results_section(client):
    resp = client.post("/search", data={"q": ""})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Results for:" not in html
    assert 'class="results"' not in html


def test_search_route_whitespace_query_no_results_section(client):
    resp = client.post("/search", data={"q": "   "})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Results for:" not in html


def test_search_route_input_persists_query(client):
    resp = client.post("/search", data={"q": "grief"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'value="grief"' in html


def test_search_route_shows_query_context_line(client):
    resp = client.post("/search", data={"q": "autumn"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Results for:" in html
    assert "autumn" in html


def test_search_route_empty_db_shows_no_poems_available(client):
    resp = client.post("/search", data={"q": "grief"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Results for:" in html
    assert "No poems available." in html


def test_search_route_renders_results(client, app, embedding_service, lexical_processor):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    create_poem(
        conn,
        "Grief Poem",
        "grief and sorrow fill the autumn air tonight",
        embedding_service,
        lexical_processor,
    )
    conn.close()

    resp = client.post("/search", data={"q": "grief"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Results for:" in html
    assert "Grief Poem" in html


def test_search_route_renders_badge(client, app, embedding_service, lexical_processor):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    create_poem(
        conn,
        "Forest Poem",
        "tall trees in a quiet forest clearing",
        embedding_service,
        lexical_processor,
    )
    conn.close()

    resp = client.post("/search", data={"q": "forest trees"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'class="badge' in html


def test_results_partial_renders_badges(client, app, embedding_service, lexical_processor):
    """Each result row contains exactly one badge element."""
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    for i in range(3):
        create_poem(
            conn,
            f"Poem {i}",
            f"unique text about rivers mountains and sky for poem {i}",
            embedding_service,
            lexical_processor,
        )
    conn.close()

    resp = client.post("/search", data={"q": "mountains rivers"})
    assert resp.status_code == 200
    html = resp.data.decode()

    badge_count = html.count('class="badge ')
    assert badge_count == 3
    assert any(f"badge-{lbl}" in html for lbl in ("strong", "moderate", "weak"))


def test_search_route_still_returns_five_results_and_preserves_query(
    client,
    app,
    embedding_service,
    lexical_processor,
):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    for i in range(6):
        create_poem(
            conn,
            f"Poem {i}",
            f"quiet light over river stone number {i}",
            embedding_service,
            lexical_processor,
        )
    conn.close()

    resp = client.post("/search", data={"q": "quiet light"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'value="quiet light"' in html
    assert html.count('class="result"') == 5


def test_search_route_untitled_for_blank_title(client, app, embedding_service):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    dim = app.extensions["embedding"].dimension
    blob = make_embedding_blob(dim)
    insert_poem_raw(conn, "", "poem about the quiet sea at dusk", blob)
    conn.close()

    app.extensions["search"].refresh()

    resp = client.post("/search", data={"q": "sea"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Untitled" in html


def test_index_shows_startup_upgrade_message_while_running(app, client, monkeypatch):
    coordinator = app.extensions["startup_upgrade"]
    monkeypatch.setattr(coordinator, "status", lambda: UpgradeStatus.running())

    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Search data is being upgraded." in html
    assert 'disabled' in html


def test_search_route_returns_503_when_startup_upgrade_failed(app, client, monkeypatch):
    coordinator = app.extensions["startup_upgrade"]
    monkeypatch.setattr(
        coordinator,
        "status",
        lambda: UpgradeStatus.failed("automatic upgrade failed"),
    )

    resp = client.post("/search", data={"q": "grief"})

    assert resp.status_code == 503
    html = resp.data.decode()
    assert "Search data upgrade failed." in html
    assert "automatic upgrade failed" in html
