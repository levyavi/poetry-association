# Poetry Association Tool

A private, offline-first semantic search tool for a curated poem collection. Enter a word or short phrase and retrieve the top five poems most semantically associated with that query, powered by a local embedding model.

The full product specification lives in [`docs/poetry_association_tool_design_document.md`](docs/poetry_association_tool_design_document.md). That document is the authoritative source for scope, constraints, and acceptance behavior.

---

## V1 Scope

Version 1 is a minimal, local-only web application with a fixed feature set:

- **Public search page** — no authentication. Enter a query, get up to 5 ranked results with fixed-threshold relevance labels (`Strong`, `Moderate`, `Weak`).
- **Result modal** — click a result to open the full poem in an overlay with preserved line breaks and a Copy button.
- **Admin page** — password-protected via environment variable. Supports:
  - Manual add / edit / delete of poems
  - CSV import with strict `title,text` format, duplicate skipping, pre-confirm counts, cancellation, and partial-preservation semantics
  - Full rebuild of all embeddings, with search and admin writes disabled during the rebuild
  - Six poem list sort orders
- **Local SQLite** for storage.
- **Local embedding model** `all-MiniLM-L6-v2` (must be pre-installed — no runtime download).
- **Windows target**, started manually via `python -m poem_assoc` and opened in a browser.

Explicitly out of V1: public user accounts, analytics, keyword highlighting, similarity explanations, backup/restore, export, cloud APIs, keyboard navigation beyond Enter-to-search, and anything else listed as "Non-goals" in design doc §2.2 or "Future work" in §18.

---

## Architecture Overview

```
┌────────────────────────┐
│ Browser (search page)  │──── POST /search ────┐
│   + result modal       │                       │
│   + admin pages        │                       ▼
└────────────┬───────────┘          ┌────────────────────────┐
             │                      │ Flask app (synchronous)│
             │   GET /poems/<id>    │                        │
             └──────────────────────┤  public blueprint      │
                                    │  admin blueprint       │
                                    │                        │
                                    │  ┌──────────────────┐  │
                                    │  │ SearchService    │  │
                                    │  │  (in-memory      │  │
                                    │  │   embedding      │  │
                                    │  │   cache)         │  │
                                    │  └───────┬──────────┘  │
                                    │          │             │
                                    │  ┌───────▼──────────┐  │
                                    │  │ EmbeddingService │  │
                                    │  │  all-MiniLM-L6-v2│  │
                                    │  └───────┬──────────┘  │
                                    │          │             │
                                    │  ┌───────▼──────────┐  │
                                    │  │ Repository       │  │
                                    │  └───────┬──────────┘  │
                                    │          │             │
                                    │     SQLite (poems.db)  │
                                    │                        │
                                    │  RebuildLock gates     │
                                    │  search + mutations    │
                                    └────────────────────────┘
```

Key modules (fully listed in the file system layout below):

| Layer              | Module                                | Responsibility                                                                 |
|--------------------|---------------------------------------|--------------------------------------------------------------------------------|
| Entry              | `poem_assoc.__main__`                 | CLI dispatch: runserver (default) or `import-csv`                              |
| App                | `poem_assoc.app`                      | `create_app` factory — wires config, DB, embedding, search, locks, blueprints  |
| Config             | `poem_assoc.config`                   | Env-driven configuration dataclass                                             |
| Persistence        | `poem_assoc.db`, `poem_assoc.repository` | SQLite schema + poem CRUD                                                    |
| Text               | `poem_assoc.text_cleaning`            | Cleaning, dedup key, query normalization                                       |
| Embeddings         | `poem_assoc.embedding`                | Loads `all-MiniLM-L6-v2` once per process, encodes, (de)serializes             |
| Search             | `poem_assoc.search`, `poem_assoc.constants` | Cosine ranking, relevance labels, in-memory cache                          |
| CSV import         | `poem_assoc.csv_import`, `poem_assoc.import_state` | Strict parser, plan/execute split, cancellation                        |
| Admin              | `poem_assoc.routes.admin`             | Login, dashboard, CRUD, CSV import UI, rebuild button                          |
| Auth + CSRF        | `poem_assoc.auth`, `poem_assoc.csrf`  | Password session auth, timing-safe compare, per-session CSRF token             |
| Rebuild + locks    | `poem_assoc.rebuild`, `poem_assoc.locks` | Full rebuild + process-wide `RebuildLock`                                   |

---

## File System Layout (V1)

```
poem_assoc/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── poem_assoc.db               (generated at runtime, gitignored)
├── docs/
│   ├── poetry_association_tool_design_document.md
│   ├── task_tempalte.md
│   └── todo.md
├── tasks/
│   ├── 001.md
│   ├── 002.md
│   ├── 003.md
│   ├── 004.md
│   ├── 005.md
│   ├── 006.md
│   ├── 007.md
│   └── 008.md
├── sample_data/
│   └── sample_poems.csv
├── src/
│   └── poem_assoc/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── config.py
│       ├── db.py
│       ├── text_cleaning.py
│       ├── embedding.py
│       ├── repository.py
│       ├── constants.py
│       ├── search.py
│       ├── csv_import.py
│       ├── import_state.py
│       ├── auth.py
│       ├── csrf.py
│       ├── locks.py
│       ├── rebuild.py
│       ├── cli.py
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── public.py
│       │   └── admin.py
│       ├── templates/
│       │   ├── base.html
│       │   ├── search.html
│       │   ├── _results.html
│       │   ├── _poem_modal.html
│       │   └── admin/
│       │       ├── _base.html
│       │       ├── login.html
│       │       ├── dashboard.html
│       │       ├── add.html
│       │       ├── edit.html
│       │       ├── delete_confirm.html
│       │       ├── import_upload.html
│       │       ├── import_preview.html
│       │       ├── import_result.html
│       │       └── rebuild_result.html
│       └── static/
│           ├── css/
│           │   └── styles.css
│           └── js/
│               └── search.js
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   ├── __init__.py
    │   ├── fixture_poems.csv
    │   ├── fixture_import.csv
    │   ├── fixture_import_bad_headers.csv
    │   └── fixture_import_partial_failure.csv
    ├── test_scaffold.py
    ├── test_text_cleaning.py
    ├── test_embedding.py
    ├── test_repository.py
    ├── test_csv_import.py
    ├── test_cli_import.py
    ├── test_search_service.py
    ├── test_search_route.py
    ├── test_poem_route.py
    ├── test_modal_partial.py
    ├── test_auth.py
    ├── test_admin_dashboard.py
    ├── test_csrf.py
    ├── test_admin_add.py
    ├── test_admin_edit.py
    ├── test_admin_delete.py
    ├── test_admin_import_upload.py
    ├── test_admin_import_execute.py
    ├── test_admin_import_cancellation.py
    ├── test_locks.py
    ├── test_rebuild.py
    └── test_rebuild_route_gating.py
```

---

## Execution Plan

Tasks are executed strictly in order. Each task produces an observable outcome and leaves the system runnable. See the matching file under `tasks/NNN.md` for the full specification.

| # | Task                                                                 | Complexity | Observable Outcome                                                                 |
|---|----------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------|
| 001 | Project scaffold and runnable Flask search page shell              | Medium     | `python -m poem_assoc` serves the search page; SQLite schema is created            |
| 002 | Text cleaning, embedding service, repository, CSV import CLI       | High       | `python -m poem_assoc import-csv sample.csv` populates DB with embeddings          |
| 003 | Search pipeline and results rendering with relevance labels        | Medium     | Typing a query returns up to 5 labeled results                                     |
| 004 | Poem modal with Copy button                                        | Low        | Clicking a result opens the full poem; Copy button works                           |
| 005 | Admin authentication and sorted poem list                          | Medium     | `/admin` requires password; dashboard lists poems with six sort options            |
| 006 | Admin manual add / edit / delete with embedding regeneration       | High       | Admin can fully CRUD poems; duplicates blocked; search stays consistent            |
| 007 | Admin CSV import with pre-confirm counts and cancellation          | High       | Admin uploads CSV, sees counts, confirms; cancellation and partial failure handled |
| 008 | Rebuild all embeddings with application lock                       | High       | Rebuild button regenerates embeddings; search and admin writes blocked during      |

**Dependency graph** (forward-only):

```
001 → 002 → 003 → 004
         ↘
           005 → 006 → 007 → 008
```

### Dependency reasoning

- **001 → everything**: all later tasks depend on the app factory, config, and schema.
- **002 → 003**: search uses the embedding service and repository, and expects non-empty data.
- **003 → 004**: the modal is wired to the result row elements that 003 renders.
- **002 + 001 → 005**: the admin dashboard uses the repository (002) and the config-driven password (001).
- **003 + 005 → 006**: admin CRUD invalidates the search cache added in 003 and is registered on the admin blueprint from 005.
- **002 + 006 → 007**: CSV import UI reuses the `plan`/`execute` split (002) and the CSRF + flash infrastructure (006).
- **006 + 007 → 008**: the rebuild lock must gate every mutation route introduced in 006 and 007 plus the public search from 003.

Every task can be implemented without modifying future tasks, and every task leaves the system in a valid, runnable state.

---

## Running the App

```bash
# First-time setup (in a virtualenv)
pip install -e .

# Ensure the embedding model is available locally
# (pre-download into the sentence-transformers cache or point POEM_MODEL_PATH at a local directory)

# Set the admin password
export POEM_ADMIN_PASSWORD="<your-private-password>"      # Linux / macOS
$env:POEM_ADMIN_PASSWORD = "<your-private-password>"      # PowerShell

# Run the server
python -m poem_assoc
# → http://localhost:5000/

# Load poems from a CSV file via the CLI
python -m poem_assoc import-csv sample_data/sample_poems.csv
```

---

## Testing Strategy

The test suite is built around the constraints in design doc §15 and the testing rules in the task template.

1. **Real SQLite for every persistence test.** Each test uses a pytest `tmp_path` to create a fresh DB file; no in-memory connections, no mocked rows.
2. **Real filesystem for CSV tests.** Fixture CSVs live under `tests/fixtures/` and are opened by the import code exactly as production would.
3. **Real local embedding model.** A session-scoped fixture loads `all-MiniLM-L6-v2` once and shares it across tests. This gives honest coverage of the encoding pipeline without repeated model-load cost.
4. **Mocks are avoided** except for small injection points that cannot be exercised any other way:
   - Forced-failure tests for the rebuild loop and the CSV import partial-failure case monkey-patch `repository.create_poem` / the embedding service to raise on a specific row.
   - Cancellation tests inject a `cancel_flag` callable.
5. **End-to-end coverage**: integration tests drive the Flask test client through the real request pipeline for every route — public search, modal JSON fetch, admin login, admin CRUD, admin CSV import, and admin rebuild.
6. **Deterministic ranking tests** may write synthetic embedding vectors directly into the repository via a test helper so that tie-breaking and label threshold tests are not dependent on the exact outputs of the model.

### Test layering

- **Unit tests**: text cleaning rules, dedup key normalization, query normalization, label thresholds, embedding serialization, CSRF token, lock semantics.
- **Integration tests**: repository, search service, CSV planner and executor, every Flask route.
- **Filesystem tests**: DB file creation, CSV import cleanup, temp file lifecycle.
- **Persistence tests**: direct SQLite queries to verify state after writes, cancellation, and rebuild.
- **UI tests**: Jinja template rendering assertions (badges, flash messages, CSRF tokens, `Untitled` fallback, modal structure).
- **Performance smoke tests**: generous bounds (e.g., "import 10 poems in under 10 seconds") to catch pathological regressions without becoming flaky.

Run the full suite with `pytest`.

---

## Further Reading

- Design document (authoritative scope): `docs/poetry_association_tool_design_document.md`
- Task template (required for every task file): `docs/task_tempalte.md`
- Task specs: `tasks/001.md` through `tasks/008.md`
- Full checklist: `docs/todo.md`
