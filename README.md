# Poetry Association Tool

A private, offline-first local search tool for a curated poem collection. Version 2 keeps the existing embedding-based search workflow and adds a conservative lexical signal built from bundled NLTK resources and local WordNet synonyms.

The authoritative V2 scope, constraints, and acceptance behavior live in [`docs/poetry_association_tool_v2_design_document.md`](docs/poetry_association_tool_v2_design_document.md). The required task structure lives in [`docs/task_tempalte.md`](docs/task_tempalte.md).

---

## Project Purpose

The application is a Windows-first local web app for one private poet user. It stores poems in SQLite, runs fully offline, and returns the top 5 poems for a word or short phrase query. V1 already delivers:

- semantic embedding search
- modal poem viewing
- password-protected admin CRUD
- CSV import
- rebuild with write/search gating

V2 extends that baseline with a second ranking signal while preserving the same simple public UI.

---

## V2 Scope

Version 2 is limited to the behavior defined in the V2 design document:

- Keep semantic similarity as the dominant ranking signal.
- Add exact lexical matching against persisted lemmatized poem text.
- Add conservative WordNet synonym expansion only for eligible noun/adjective query terms.
- Keep the system fully offline by bundling all required local NLP resources.
- Automatically rebuild outdated search data on startup after upgrade.
- Keep the public UI implicit: no synonym controls, no debug panel, no new search modes.
- Provide a global rollback flag for synonym expansion.
- Add local-only logging and an in-memory synonym cache for debugging and tuning.

Explicitly out of scope for V2: phrase-level thesaurus expansion, verb/adverb expansion, negation handling, user-facing explanations, admin synonym editing, remote services, or any cloud dependency.

---

## Architecture Overview

```text
┌───────────────────────────┐
│ Browser                   │
│  public search page       │
│  modal poem viewer        │
│  admin dashboard          │
└─────────────┬─────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────┐
│ Flask app                                               │
│                                                          │
│  public routes        admin routes                       │
│  startup-upgrade gate  rebuild/write gate                │
│                                                          │
│  StartupUpgradeCoordinator                              │
│          │                                               │
│          ▼                                               │
│  SearchService                                           │
│   ├─ semantic path → EmbeddingService                    │
│   ├─ lexical path  → LexicalTextProcessor                │
│   └─ synonym path  → SynonymExpander                     │
│                                                          │
│  Rebuild pipeline                                        │
│   ├─ regenerates embeddings                              │
│   ├─ regenerates lemmatized_search_text                  │
│   └─ updates search index metadata                       │
└─────────────┬────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────┐
│ SQLite                                                  │
│  poems                                                  │
│   - id, title, text, cleaned_text, embedding            │
│   - lemmatized_search_text                              │
│  app_metadata                                           │
│   - schema_version                                      │
│   - search_index_version                                │
│   - last_successful_full_rebuild_at                     │
└──────────────────────────────────────────────────────────┘
```

### Key V2 runtime modules

| Module | Responsibility |
|---|---|
| `poem_assoc.lexical` | shared normalization, lemmatization, lexical text generation, query-term building |
| `poem_assoc.index_metadata` | search index compatibility state and rebuild metadata |
| `poem_assoc.startup_upgrade` | automatic first-start rebuild coordination |
| `poem_assoc.search` | corpus-wide semantic + lexical + synonym scoring |
| `poem_assoc.synonyms` | conservative local WordNet expansion |
| `poem_assoc.rebuild` | full regeneration of embeddings and lexical derived data |

---

## V2 Roadmap

### Major workstreams

1. **Offline NLP and lexical index foundation**  
   Bundle local NLTK resources, add persisted `lemmatized_search_text`, and regenerate it on every write path.

2. **Upgrade orchestration and safe availability gating**  
   Detect outdated search indexes on startup, rebuild automatically, and keep search/admin writes blocked until the upgrade completes.

3. **Combined ranking with exact lexical evidence**  
   Move from semantic-only ranking to full-corpus combined scoring while keeping the public UI unchanged.

4. **Conservative synonym expansion with rollback control**  
   Add noun/adjective-only WordNet expansion behind a config flag.

5. **Diagnostics, cache behavior, and regression hardening**  
   Add required local logging, process-lifetime synonym caching, and deterministic acceptance coverage.

### Dependency graph

```text
008 → 009 → 010 → 011 → 012 → 013
```

### Ordered tasks

| # | Task | Complexity | Observable Outcome |
|---|---|---|---|
| 009 | Persist lemmatized search text and bundle offline NLP resources | High | DB schema gains `lemmatized_search_text` + metadata; all write paths regenerate lexical derived data |
| 010 | Automatic startup rebuild for outdated search indexes | High | Old installs auto-rebuild on startup; search/admin writes are gated with clear status messaging |
| 011 | Exact lexical matching and combined search ranking | Medium | Search ranking and labels switch to full combined scoring while UI stays the same |
| 012 | WordNet synonym expansion with configurable lexical boost | High | Synonym-only matches improve recall; `ENABLE_SYNONYM_EXPANSION` provides rollback |
| 013 | Synonym cache, search diagnostics, and V2 regression hardening | Medium | Repeated searches reuse cached expansions; local logs and deterministic regression coverage exist |

### Dependency reasoning

- `009` comes first because every later V2 feature depends on persisted lexical text and search-index metadata.
- `010` must precede ranking changes so migrated V1 databases are rebuilt before search consumes V2 fields.
- `011` introduces combined scoring with the lowest-risk lexical slice: exact matches only.
- `012` adds synonyms only after combined exact lexical scoring is stable, which keeps synonym regressions isolated and rollback-safe.
- `013` finishes the design-doc requirements that are operational rather than functional: cache behavior, logging, and final regression coverage.

Every task is intended to leave the system runnable, integrated, and dependency-correct without relying on future tasks.

---

## Final File System Layout (V2)

```text
poem_assoc/
├── README.md
├── pyproject.toml
├── docs/
│   ├── poetry_association_tool_design_document.md
│   ├── poetry_association_tool_v2_design_document.md
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
│   ├── 008.md
│   ├── 009.md
│   ├── 010.md
│   ├── 011.md
│   ├── 012.md
│   └── 013.md
├── sample_data/
│   └── sample_poems.csv
├── src/
│   └── poem_assoc/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── auth.py
│       ├── cli.py
│       ├── config.py
│       ├── constants.py
│       ├── csrf.py
│       ├── csv_import.py
│       ├── db.py
│       ├── embedding.py
│       ├── import_state.py
│       ├── index_metadata.py
│       ├── lexical.py
│       ├── locks.py
│       ├── rebuild.py
│       ├── repository.py
│       ├── search.py
│       ├── startup_upgrade.py
│       ├── synonyms.py
│       ├── text_cleaning.py
│       ├── resources/
│       │   └── nltk_data/
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── admin.py
│       │   └── public.py
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
    ├── fixtures/
    │   ├── fixture_poems.csv
    │   ├── fixture_v2_exact.csv
    │   ├── fixture_v2_synonyms.csv
    │   └── fixture_v2_regression.csv
    ├── test_lexical.py
    ├── test_index_metadata.py
    ├── test_startup_upgrade.py
    ├── test_search_v2_exact.py
    ├── test_synonyms.py
    ├── test_search_diagnostics.py
    ├── test_v2_regression.py
    └── ... existing V1 tests updated as needed
```

---

## Execution Plan

Implementation should follow the tasks exactly in numeric order:

1. Build the lexical data foundation and ship bundled local NLP resources.
2. Add automatic upgrade rebuild so old installs are safe before search starts using V2 data.
3. Switch ranking to combined semantic + exact lexical scoring.
4. Layer in conservative synonym expansion with the rollback flag.
5. Finish with cache/logging/regression hardening.

This order prevents forward dependencies and avoids modifying future tasks to make earlier tasks workable.

---

## Testing Strategy

The V2 test plan stays aligned with the task template and the design document:

1. Use real SQLite files for all persistence tests.
2. Use real filesystem fixture CSVs for import and regression coverage.
3. Use bundled local NLTK resources and the real local embedding model; no runtime downloads.
4. Avoid mocks unless strictly necessary for forced-failure paths that cannot be exercised otherwise.
5. Keep search tests deterministic by using curated fixture corpora and the existing deterministic helpers where needed.
6. Cover both feature behavior and lifecycle behavior:
   - lexical data generation on add/edit/import/rebuild
   - automatic startup rebuild
   - exact lexical ranking
   - synonym ranking
   - cache/logging behavior
   - final V2 acceptance and determinism

Run the full suite with `pytest`.

---

## Running the App

```bash
pip install -e .[dev]
python -m poem_assoc
```

Operational constraints:

- the sentence-transformers model must already exist locally
- the bundled NLTK resources must be present locally
- the app must remain fully offline at runtime

---

## Further Reading

- Authoritative V2 spec: `docs/poetry_association_tool_v2_design_document.md`
- Required task structure: `docs/task_tempalte.md`
- V2 task specs: `tasks/009.md` through `tasks/013.md`
- Checklist: `docs/todo.md`
