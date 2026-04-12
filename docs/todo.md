# Poetry Association Tool — V1 TODO Checklist

This checklist is the full, sequential set of items needed to build V1, derived from tasks 001–008. Follow the task files in `/tasks/` for the full specs; this list is a quick progress tracker.

---

## Task 001 — Project Scaffold and Runnable Search Page Shell

- [x] **001** — complete

### Project setup
- [x] Create `pyproject.toml` with Flask and pytest dependencies.
- [x] Create `.gitignore` covering `*.db`, `__pycache__`, `.venv`, `.pytest_cache`, temp upload dirs.
- [x] Create `.env.example` documenting `POEM_ADMIN_PASSWORD`, `POEM_DB_PATH`, `POEM_SECRET_KEY`.
- [x] Create `sample_data/.gitkeep`.

### Source modules
- [x] `src/poem_assoc/__init__.py`.
- [x] `src/poem_assoc/__main__.py` running the Flask dev server.
- [x] `src/poem_assoc/config.py` with `Config` dataclass and `from_environment`.
- [x] `src/poem_assoc/db.py` with `init_db` and `get_connection`.
- [x] `src/poem_assoc/app.py` with `create_app` that calls `init_db`.
- [x] `src/poem_assoc/routes/__init__.py`.
- [x] `src/poem_assoc/routes/public.py` with `GET /`.

### Templates and static
- [x] `templates/base.html` with viewport meta, `{% block title %}`, `{% block content %}`.
- [x] `templates/search.html` extending base, empty form with autofocus.
- [x] `static/css/styles.css` with responsive baseline.

### Schema
- [x] `poems` table with `id, title, text, cleaned_text, embedding, created_at, updated_at`.
- [x] `idx_poems_cleaned_text` index.
- [x] `init_db` idempotent.

### Tests
- [x] `tests/conftest.py` with `temp_db_path`, `app`, `client` fixtures.
- [x] `tests/test_scaffold.py` covering config, init_db, create_app, and search page markup.
- [x] Smoke tests pass.
- [x] Observable: `python -m poem_assoc` serves the search page on localhost:5000.

---

## Task 002 — Text Cleaning, Embedding Service, Repository, and CSV Import CLI

- [x] **002** — complete

### Core modules
- [x] `text_cleaning.py` with `clean_poem_text`, `compute_dedup_key`, `clean_query`.
- [x] `embedding.py` with `EmbeddingService` (model loaded once, `encode`, `encode_query`, `to_bytes`, `from_bytes`).
- [x] `repository.py` with `create_poem`, `get_poem`, `list_poems`, `find_by_cleaned_text`; `DuplicatePoemError`.
- [x] `csv_import.py` with `plan`, `execute`, `ImportPlan`, `ImportResult`, `CsvFormatError`.
- [x] `cli.py` with the `import-csv` subcommand.
- [x] Update `__main__.py` to dispatch `import-csv` to CLI.
- [x] Update `app.py` to instantiate `EmbeddingService` at startup and attach to `app.extensions`.
- [x] Update `config.py` with `model_name`, `model_path`.
- [x] Update `pyproject.toml` with `sentence-transformers`, `numpy`.

### Sample data
- [x] `sample_data/sample_poems.csv` with ≥10 poems including duplicates.
- [x] `tests/fixtures/fixture_poems.csv` for deterministic tests.

### Tests
- [x] `test_text_cleaning.py`.
- [x] `test_embedding.py` (unit-normalization, determinism, serialization).
- [x] `test_repository.py` (insert, duplicate rejection, sort).
- [x] `test_csv_import.py` (plan, execute, cancellation, partial failure).
- [x] `test_cli_import.py` (real subprocess invocation).
- [x] All tests pass with real SQLite + real model.
- [x] Observable: CLI imports sample CSV, DB has rows with non-null embeddings.

---

## Task 003 — Search Pipeline and Results Rendering

- [x] **003** — complete

### Modules
- [x] `constants.py` with threshold values and `label_for`.
- [x] `search.py` with `SearchService`, `SearchResult`, preview truncation.
- [x] Update `repository.py` with `iter_embeddings`.
- [x] Update `app.py` to attach `SearchService`.
- [x] Update `routes/public.py` with `POST /search`.

### Templates and CSS
- [x] `_results.html` partial.
- [x] Update `search.html` to include results and preserve query value.
- [x] Update `styles.css` with results list, relevance badges, hover highlight.
- [x] Query context line `Results for: "..."`.

### Tests
- [x] `test_search_service.py` covering labels, tie-break, empty query, fewer-than-5 corpus.
- [x] `test_search_route.py` covering POST + rendering + input persistence.
- [x] `tests/fixtures/__init__.py` helpers for synthetic vectors.
- [x] Observable: typing a query on the search page returns up to 5 labeled results.

---

## Task 004 — Poem Modal with Copy Button

- [x] **004** — complete

### Route and templates
- [x] `GET /poems/<int:id>` JSON route.
- [x] `_poem_modal.html` partial included at end of `search.html`.
- [x] Include `static/js/search.js` in the page.
- [x] Add `role`, `tabindex`, `data-poem-id` on result rows.

### JavaScript
- [x] `search.js` with `initModal`, `openModal`, `closeModal`, `copyPoem`.
- [x] Escape-to-close, backdrop-to-close, close-button-to-close.
- [x] Clipboard API with `document.execCommand` fallback.
- [x] In-flight `AbortController` on rapid clicks.

### CSS
- [x] Modal overlay, card, `white-space: pre-wrap` body, responsive widths.

### Tests
- [x] `test_poem_route.py` (200 with JSON, 404 for missing, line breaks preserved).
- [x] `test_modal_partial.py` (required elements present).
- [x] Observable: clicking a result opens modal; Copy copies to clipboard.

---

## Task 005 — Admin Authentication and Sorted Poem List

- [x] **005** — complete

### Modules
- [x] `auth.py` with `is_authenticated`, `login`, `logout`, `verify_password`, `login_required`.
- [x] `routes/admin.py` with login / logout / dashboard views.
- [x] Update `app.py` to register admin blueprint and validate `POEM_ADMIN_PASSWORD` is non-empty.
- [x] Update `repository.list_poems` to accept `order_by` with a whitelist.

### Templates
- [x] `admin/_base.html` shared layout.
- [x] `admin/login.html`.
- [x] `admin/dashboard.html` with sort dropdown and placeholder action columns.
- [x] Admin CSS additions.

### Tests
- [x] `test_auth.py` (verify_password, empty-env rejection, session helpers).
- [x] `test_admin_dashboard.py` (redirect when unauthenticated, login flow, dashboard render, sort options, logout).
- [x] Public routes still work unauthenticated.
- [x] Observable: `/admin` requires password, dashboard shows sorted poem list.

---

## Task 006 — Admin Manual Add / Edit / Delete with Embedding Regeneration

- [x] **006** — complete

### Modules
- [x] `csrf.py` with `issue_token`, `verify_token`, registered Jinja global.
- [x] Update `repository.py` with `update_poem`, `delete_poem`, `PoemNotFoundError`.
- [x] Update `routes/admin.py` with add / edit / delete views (GET + POST + confirm).
- [x] `SearchService.refresh()` called after every successful mutation.

### Templates
- [x] `admin/add.html`.
- [x] `admin/edit.html` pre-populated.
- [x] `admin/delete_confirm.html` showing preview.
- [x] Update dashboard to link add / edit / delete.
- [x] Flash messages rendered in `admin/_base.html`.
- [x] CSS for forms and confirmation.

### Tests
- [x] `test_csrf.py`.
- [x] `test_admin_add.py` (success, duplicate blocked, empty text blocked).
- [x] `test_admin_edit.py` (success, duplicate blocked, 404 missing).
- [x] `test_admin_delete.py` (confirm flow, row removed).
- [x] Mutation routes require auth + CSRF.
- [x] Observable: admin can fully CRUD poems; changes visible in search.

---

## Task 007 — CSV Import Admin UI with Pre-Confirm and Cancellation

- [x] **007** — complete

### Modules
- [x] `import_state.py` with `ImportSession`, `create`, `get`, `cancel`, `discard`, `cleanup_expired`.
- [x] Update `csv_import.execute` to honor `cancel_flag` and `on_progress` (no-op by default).
- [x] Update `routes/admin.py` with `import_upload`, `import_preview`, `import_confirm`, `import_cancel`.
- [x] Update `config.py` with `import_temp_dir`.
- [x] `admin/_base.html` nav link to Import CSV.
- [x] CSS for upload / preview / result screens.

### Templates
- [x] `admin/import_upload.html`.
- [x] `admin/import_preview.html`.
- [x] `admin/import_result.html`.

### Fixtures
- [x] `tests/fixtures/fixture_import.csv` with duplicates.
- [x] `tests/fixtures/fixture_import_bad_headers.csv`.
- [x] `tests/fixtures/fixture_import_partial_failure.csv`.

### Tests
- [x] `test_admin_import_upload.py` (preview counts, bad headers rejected, auth, CSRF).
- [x] `test_admin_import_execute.py` (confirm writes rows, duplicates skipped, temp cleanup, search cache refresh).
- [x] `test_admin_import_cancellation.py` (cancel mid-import preserves prior rows).
- [x] Partial failure fixture preserves rows 1..K-1.
- [x] Observable: admin uploads CSV, sees counts, confirms, and poems appear in search.

---

## Task 008 — Rebuild All Embeddings with Application Lock

- [x] **008** — complete

### Modules
- [x] `locks.py` with `RebuildLock` (thread-safe acquire/release/is_rebuilding).
- [x] `rebuild.py` with `run_rebuild` iterating every poem.
- [x] `admin.rebuild_all` POST view (acquire → run → refresh → release).
- [x] `public.search` checks lock; returns 503 when rebuilding.
- [x] `admin.reject_if_rebuilding` helper wired into every mutation view (add, edit, delete, import preview, confirm, cancel).

### Templates
- [x] Dashboard `Rebuild all embeddings` button (CSRF).
- [x] `admin/rebuild_result.html`.
- [x] Rebuild-in-progress banner in `admin/_base.html`.
- [x] Search 503 page message.
- [x] CSS for banner and result.

### Tests
- [x] `test_locks.py` (acquire/release semantics, second-acquire fails, release-without-acquire safe).
- [x] `test_rebuild.py` (all embeddings regenerated, partial failure commits prior rows, row count unchanged).
- [x] `test_rebuild_route_gating.py` (search 503, every mutation blocked, second rebuild rejected, lock released on failure).
- [x] Observable: rebuild button refreshes every embedding; concurrent search/admin writes are blocked during rebuild.

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
