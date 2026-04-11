# Poetry Association Tool — V1 TODO Checklist

This checklist is the full, sequential set of items needed to build V1, derived from tasks 001–008. Follow the task files in `/tasks/` for the full specs; this list is a quick progress tracker.

---

## Task 001 — Project Scaffold and Runnable Search Page Shell

### Project setup
- [ ] Create `pyproject.toml` with Flask and pytest dependencies.
- [ ] Create `.gitignore` covering `*.db`, `__pycache__`, `.venv`, `.pytest_cache`, temp upload dirs.
- [ ] Create `.env.example` documenting `POEM_ADMIN_PASSWORD`, `POEM_DB_PATH`, `POEM_SECRET_KEY`.
- [ ] Create `sample_data/.gitkeep`.

### Source modules
- [ ] `src/poem_assoc/__init__.py`.
- [ ] `src/poem_assoc/__main__.py` running the Flask dev server.
- [ ] `src/poem_assoc/config.py` with `Config` dataclass and `from_environment`.
- [ ] `src/poem_assoc/db.py` with `init_db` and `get_connection`.
- [ ] `src/poem_assoc/app.py` with `create_app` that calls `init_db`.
- [ ] `src/poem_assoc/routes/__init__.py`.
- [ ] `src/poem_assoc/routes/public.py` with `GET /`.

### Templates and static
- [ ] `templates/base.html` with viewport meta, `{% block title %}`, `{% block content %}`.
- [ ] `templates/search.html` extending base, empty form with autofocus.
- [ ] `static/css/styles.css` with responsive baseline.

### Schema
- [ ] `poems` table with `id, title, text, cleaned_text, embedding, created_at, updated_at`.
- [ ] `idx_poems_cleaned_text` index.
- [ ] `init_db` idempotent.

### Tests
- [ ] `tests/conftest.py` with `temp_db_path`, `app`, `client` fixtures.
- [ ] `tests/test_scaffold.py` covering config, init_db, create_app, and search page markup.
- [ ] Smoke tests pass.
- [ ] Observable: `python -m poem_assoc` serves the search page on localhost:5000.

---

## Task 002 — Text Cleaning, Embedding Service, Repository, and CSV Import CLI

### Core modules
- [ ] `text_cleaning.py` with `clean_poem_text`, `compute_dedup_key`, `clean_query`.
- [ ] `embedding.py` with `EmbeddingService` (model loaded once, `encode`, `encode_query`, `to_bytes`, `from_bytes`).
- [ ] `repository.py` with `create_poem`, `get_poem`, `list_poems`, `find_by_cleaned_text`; `DuplicatePoemError`.
- [ ] `csv_import.py` with `plan`, `execute`, `ImportPlan`, `ImportResult`, `CsvFormatError`.
- [ ] `cli.py` with the `import-csv` subcommand.
- [ ] Update `__main__.py` to dispatch `import-csv` to CLI.
- [ ] Update `app.py` to instantiate `EmbeddingService` at startup and attach to `app.extensions`.
- [ ] Update `config.py` with `model_name`, `model_path`.
- [ ] Update `pyproject.toml` with `sentence-transformers`, `numpy`.

### Sample data
- [ ] `sample_data/sample_poems.csv` with ≥10 poems including duplicates.
- [ ] `tests/fixtures/fixture_poems.csv` for deterministic tests.

### Tests
- [ ] `test_text_cleaning.py`.
- [ ] `test_embedding.py` (unit-normalization, determinism, serialization).
- [ ] `test_repository.py` (insert, duplicate rejection, sort).
- [ ] `test_csv_import.py` (plan, execute, cancellation, partial failure).
- [ ] `test_cli_import.py` (real subprocess invocation).
- [ ] All tests pass with real SQLite + real model.
- [ ] Observable: CLI imports sample CSV, DB has rows with non-null embeddings.

---

## Task 003 — Search Pipeline and Results Rendering

### Modules
- [ ] `constants.py` with threshold values and `label_for`.
- [ ] `search.py` with `SearchService`, `SearchResult`, preview truncation.
- [ ] Update `repository.py` with `iter_embeddings`.
- [ ] Update `app.py` to attach `SearchService`.
- [ ] Update `routes/public.py` with `POST /search`.

### Templates and CSS
- [ ] `_results.html` partial.
- [ ] Update `search.html` to include results and preserve query value.
- [ ] Update `styles.css` with results list, relevance badges, hover highlight.
- [ ] Query context line `Results for: "..."`.

### Tests
- [ ] `test_search_service.py` covering labels, tie-break, empty query, fewer-than-5 corpus.
- [ ] `test_search_route.py` covering POST + rendering + input persistence.
- [ ] `tests/fixtures/__init__.py` helpers for synthetic vectors.
- [ ] Observable: typing a query on the search page returns up to 5 labeled results.

---

## Task 004 — Poem Modal with Copy Button

### Route and templates
- [ ] `GET /poems/<int:id>` JSON route.
- [ ] `_poem_modal.html` partial included at end of `search.html`.
- [ ] Include `static/js/search.js` in the page.
- [ ] Add `role`, `tabindex`, `data-poem-id` on result rows.

### JavaScript
- [ ] `search.js` with `initModal`, `openModal`, `closeModal`, `copyPoem`.
- [ ] Escape-to-close, backdrop-to-close, close-button-to-close.
- [ ] Clipboard API with `document.execCommand` fallback.
- [ ] In-flight `AbortController` on rapid clicks.

### CSS
- [ ] Modal overlay, card, `white-space: pre-wrap` body, responsive widths.

### Tests
- [ ] `test_poem_route.py` (200 with JSON, 404 for missing, line breaks preserved).
- [ ] `test_modal_partial.py` (required elements present).
- [ ] Observable: clicking a result opens modal; Copy copies to clipboard.

---

## Task 005 — Admin Authentication and Sorted Poem List

### Modules
- [ ] `auth.py` with `is_authenticated`, `login`, `logout`, `verify_password`, `login_required`.
- [ ] `routes/admin.py` with login / logout / dashboard views.
- [ ] Update `app.py` to register admin blueprint and validate `POEM_ADMIN_PASSWORD` is non-empty.
- [ ] Update `repository.list_poems` to accept `order_by` with a whitelist.

### Templates
- [ ] `admin/_base.html` shared layout.
- [ ] `admin/login.html`.
- [ ] `admin/dashboard.html` with sort dropdown and placeholder action columns.
- [ ] Admin CSS additions.

### Tests
- [ ] `test_auth.py` (verify_password, empty-env rejection, session helpers).
- [ ] `test_admin_dashboard.py` (redirect when unauthenticated, login flow, dashboard render, sort options, logout).
- [ ] Public routes still work unauthenticated.
- [ ] Observable: `/admin` requires password, dashboard shows sorted poem list.

---

## Task 006 — Admin Manual Add / Edit / Delete with Embedding Regeneration

### Modules
- [ ] `csrf.py` with `issue_token`, `verify_token`, registered Jinja global.
- [ ] Update `repository.py` with `update_poem`, `delete_poem`, `PoemNotFoundError`.
- [ ] Update `routes/admin.py` with add / edit / delete views (GET + POST + confirm).
- [ ] `SearchService.refresh()` called after every successful mutation.

### Templates
- [ ] `admin/add.html`.
- [ ] `admin/edit.html` pre-populated.
- [ ] `admin/delete_confirm.html` showing preview.
- [ ] Update dashboard to link add / edit / delete.
- [ ] Flash messages rendered in `admin/_base.html`.
- [ ] CSS for forms and confirmation.

### Tests
- [ ] `test_csrf.py`.
- [ ] `test_admin_add.py` (success, duplicate blocked, empty text blocked).
- [ ] `test_admin_edit.py` (success, duplicate blocked, 404 missing).
- [ ] `test_admin_delete.py` (confirm flow, row removed).
- [ ] Mutation routes require auth + CSRF.
- [ ] Observable: admin can fully CRUD poems; changes visible in search.

---

## Task 007 — CSV Import Admin UI with Pre-Confirm and Cancellation

### Modules
- [ ] `import_state.py` with `ImportSession`, `create`, `get`, `cancel`, `discard`, `cleanup_expired`.
- [ ] Update `csv_import.execute` to honor `cancel_flag` and `on_progress` (no-op by default).
- [ ] Update `routes/admin.py` with `import_upload`, `import_preview`, `import_confirm`, `import_cancel`.
- [ ] Update `config.py` with `import_temp_dir`.
- [ ] `admin/_base.html` nav link to Import CSV.
- [ ] CSS for upload / preview / result screens.

### Templates
- [ ] `admin/import_upload.html`.
- [ ] `admin/import_preview.html`.
- [ ] `admin/import_result.html`.

### Fixtures
- [ ] `tests/fixtures/fixture_import.csv` with duplicates.
- [ ] `tests/fixtures/fixture_import_bad_headers.csv`.
- [ ] `tests/fixtures/fixture_import_partial_failure.csv`.

### Tests
- [ ] `test_admin_import_upload.py` (preview counts, bad headers rejected, auth, CSRF).
- [ ] `test_admin_import_execute.py` (confirm writes rows, duplicates skipped, temp cleanup, search cache refresh).
- [ ] `test_admin_import_cancellation.py` (cancel mid-import preserves prior rows).
- [ ] Partial failure fixture preserves rows 1..K-1.
- [ ] Observable: admin uploads CSV, sees counts, confirms, and poems appear in search.

---

## Task 008 — Rebuild All Embeddings with Application Lock

### Modules
- [ ] `locks.py` with `RebuildLock` (thread-safe acquire/release/is_rebuilding).
- [ ] `rebuild.py` with `run_rebuild` iterating every poem.
- [ ] `admin.rebuild_all` POST view (acquire → run → refresh → release).
- [ ] `public.search` checks lock; returns 503 when rebuilding.
- [ ] `admin.reject_if_rebuilding` helper wired into every mutation view (add, edit, delete, import preview, confirm, cancel).

### Templates
- [ ] Dashboard `Rebuild all embeddings` button (CSRF).
- [ ] `admin/rebuild_result.html`.
- [ ] Rebuild-in-progress banner in `admin/_base.html`.
- [ ] Search 503 page message.
- [ ] CSS for banner and result.

### Tests
- [ ] `test_locks.py` (acquire/release semantics, second-acquire fails, release-without-acquire safe).
- [ ] `test_rebuild.py` (all embeddings regenerated, partial failure commits prior rows, row count unchanged).
- [ ] `test_rebuild_route_gating.py` (search 503, every mutation blocked, second rebuild rejected, lock released on failure).
- [ ] Observable: rebuild button refreshes every embedding; concurrent search/admin writes are blocked during rebuild.

---

## Cross-Cutting Verification (after Task 008)

- [ ] All acceptance criteria from design doc §17 are demonstrated end-to-end on Windows with no network access.
- [ ] App starts with `python -m poem_assoc` and is reachable at `http://localhost:5000/`.
- [ ] Public search page works unauthenticated; admin page requires the env-configured password.
- [ ] Add, edit, delete, CSV import, and rebuild all work from the admin UI.
- [ ] Duplicates are blocked based on cleaned text, case-sensitive, for both manual save and CSV import.
- [ ] Partial CSV imports are preserved on failure and on cancellation.
- [ ] Rebuild disables search and admin writes for the duration.
- [ ] `pytest` full suite passes with real SQLite and the real local model.
