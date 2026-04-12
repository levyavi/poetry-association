"""Integration and UI tests for the admin authentication gate and dashboard."""
import pytest

from poem_assoc.app import create_app
from poem_assoc.config import Config
from poem_assoc import repository
from poem_assoc.startup_upgrade import UpgradeStatus

TEST_PASSWORD = "test-pass"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client):
    return client.post("/admin/login", data={"password": TEST_PASSWORD}, follow_redirects=False)


def _insert_poem(db_path, title, text="poem body", created_at=None, updated_at=None):
    """Insert a bare poem row directly for test setup."""
    from poem_assoc.db import get_connection
    now = created_at or "2024-01-01T00:00:00+00:00"
    upd = updated_at or now
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
        "VALUES (?, ?, '', NULL, ?, ?)",
        (title, text, now, upd),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Startup guard
# ---------------------------------------------------------------------------

class TestStartupGuard:
    def test_empty_password_raises(self, temp_db_path, embedding_service):
        cfg = Config(
            db_path=temp_db_path,
            secret_key="test-secret",
            admin_password="",
            model_name="all-MiniLM-L6-v2",
            model_path=None,
        )
        with pytest.raises(RuntimeError, match="POEM_ADMIN_PASSWORD must be set"):
            create_app(config_override=cfg, embedding_service=embedding_service)


# ---------------------------------------------------------------------------
# Authentication flow
# ---------------------------------------------------------------------------

class TestAuthFlow:
    def test_admin_redirects_when_unauthenticated(self, client):
        resp = client.get("/admin/")
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_login_page_contains_password_field(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b'type="password"' in resp.data

    def test_wrong_password_rejects_and_shows_flash(self, client):
        resp = client.post("/admin/login", data={"password": "wrong"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Incorrect password" in resp.data

    def test_correct_password_redirects_to_dashboard(self, client):
        resp = _login(client)
        assert resp.status_code == 302
        assert "/admin" in resp.headers["Location"]

    def test_authenticated_can_access_dashboard(self, client):
        _login(client)
        resp = client.get("/admin/")
        assert resp.status_code == 200
        assert b"Poems" in resp.data

    def test_logout_clears_session(self, client):
        _login(client)
        resp = client.post("/admin/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Logged out" in resp.data
        # Session should be cleared
        resp2 = client.get("/admin/")
        assert resp2.status_code == 302


# ---------------------------------------------------------------------------
# Dashboard poem list
# ---------------------------------------------------------------------------

class TestDashboardList:
    def test_lists_all_poems(self, app, client):
        cfg = app.config["POEM_CONFIG"]
        _insert_poem(cfg.db_path, "Alpha")
        _insert_poem(cfg.db_path, "Beta")
        _insert_poem(cfg.db_path, "Gamma")

        _login(client)
        resp = client.get("/admin/")
        assert resp.status_code == 200
        assert b"Alpha" in resp.data
        assert b"Beta" in resp.data
        assert b"Gamma" in resp.data

    def test_untitled_poem_shows_untitled(self, app, client):
        cfg = app.config["POEM_CONFIG"]
        _insert_poem(cfg.db_path, "")  # empty title

        _login(client)
        resp = client.get("/admin/")
        assert b"Untitled" in resp.data

    def test_sort_created_desc(self, app, client):
        cfg = app.config["POEM_CONFIG"]
        _insert_poem(cfg.db_path, "Oldest",  created_at="2024-01-01T00:00:00+00:00")
        _insert_poem(cfg.db_path, "Middle",  created_at="2024-06-01T00:00:00+00:00")
        _insert_poem(cfg.db_path, "Newest",  created_at="2024-12-01T00:00:00+00:00")

        _login(client)
        resp = client.get("/admin/?sort=created_desc")
        html = resp.data.decode()
        newest_pos = html.index("Newest")
        middle_pos = html.index("Middle")
        oldest_pos = html.index("Oldest")
        assert newest_pos < middle_pos < oldest_pos

    def test_unknown_sort_falls_back_to_title_asc(self, app, client):
        cfg = app.config["POEM_CONFIG"]
        _insert_poem(cfg.db_path, "Zeta")
        _insert_poem(cfg.db_path, "Alpha")

        _login(client)
        resp = client.get("/admin/?sort=not_a_real_sort")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert html.index("Alpha") < html.index("Zeta")

    def test_dashboard_stays_visible_but_read_only_during_startup_upgrade(
        self, app, client, monkeypatch
    ):
        cfg = app.config["POEM_CONFIG"]
        _insert_poem(cfg.db_path, "Legacy")

        coordinator = app.extensions["startup_upgrade"]
        monkeypatch.setattr(coordinator, "status", lambda: UpgradeStatus.running())

        _login(client)
        resp = client.get("/admin/")

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Search data is being upgraded. Admin is read-only until the rebuild finishes." in html
        assert 'aria-disabled="true">Add poem<' in html
        assert 'aria-disabled="true">Edit<' in html

    def test_dashboard_shows_retry_rebuild_after_startup_upgrade_failure(
        self, app, client, monkeypatch
    ):
        coordinator = app.extensions["startup_upgrade"]
        monkeypatch.setattr(
            coordinator,
            "status",
            lambda: UpgradeStatus.failed("automatic upgrade failed"),
        )

        _login(client)
        resp = client.get("/admin/")

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Startup search-data upgrade failed." in html
        assert "Retry rebuild all embeddings" in html


# ---------------------------------------------------------------------------
# Persistence: all six sort keys via repository
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sort_key", [
    "title_asc", "title_desc",
    "created_asc", "created_desc",
    "updated_asc", "updated_desc",
])
def test_list_poems_all_sort_keys_valid(db_conn, sort_key):
    now = "2024-01-01T00:00:00+00:00"
    db_conn.execute(
        "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
        "VALUES ('P1', '', '', NULL, ?, ?)", (now, now)
    )
    db_conn.execute(
        "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
        "VALUES ('P2', '', '', NULL, ?, ?)", (now, now)
    )
    db_conn.commit()

    rows = repository.list_poems(db_conn, order_by=sort_key)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Public routes remain unauthenticated
# ---------------------------------------------------------------------------

class TestPublicRoutesUnaffected:
    def test_search_page_unauthenticated(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_search_post_unauthenticated(self, client):
        resp = client.post("/search", data={"q": "test"})
        assert resp.status_code == 200
