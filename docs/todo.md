# Poetry Association Tool — Delivery Checklist

This checklist is the execution tracker for the full roadmap. V1 (`001`–`008`) is already complete. V2 starts at `009` and must be implemented strictly in order.

The authoritative scope is [`docs/poetry_association_tool_v2_design_document.md`](docs/poetry_association_tool_v2_design_document.md). The authoritative task structure is [`docs/task_tempalte.md`](docs/task_tempalte.md).

---

## Completed Baseline

- [x] **001** Project scaffold and runnable Flask search page shell
- [x] **002** Text cleaning, embedding service, repository, and CSV import CLI
- [x] **003** Search pipeline and results rendering
- [x] **004** Poem modal with Copy button
- [x] **005** Admin authentication and sorted poem list
- [x] **006** Admin manual add / edit / delete with embedding regeneration
- [x] **007** CSV import admin UI with pre-confirm and cancellation
- [x] **008** Rebuild all embeddings with application lock

---

## Task 009 — Persist Lemmatized Search Text and Bundle Offline NLP Resources

- [ ] **009** complete

### Packaging and config
- [ ] Add `nltk` to runtime dependencies.
- [ ] Package bundled local NLTK resources under `src/poem_assoc/resources/nltk_data/`.
- [ ] Add config support for resolving and validating the local NLP resource path.
- [ ] Add the V2 `SEARCH_INDEX_VERSION` constant.

### Source modules
- [ ] Create `src/poem_assoc/lexical.py`.
- [ ] Create `src/poem_assoc/index_metadata.py`.
- [ ] Update `src/poem_assoc/db.py` to migrate existing V1 databases and create `app_metadata`.
- [ ] Update `src/poem_assoc/app.py` to instantiate and register the lexical processor.
- [ ] Update `src/poem_assoc/repository.py` to regenerate `lemmatized_search_text` on create and edit.
- [ ] Update `src/poem_assoc/csv_import.py` to regenerate lexical derived data during import.
- [ ] Update `src/poem_assoc/cli.py` to pass the lexical processor into CLI import execution.
- [ ] Update `src/poem_assoc/rebuild.py` to regenerate `lemmatized_search_text` and mark metadata current only on full success.
- [ ] Update `src/poem_assoc/routes/admin.py` to thread the lexical processor through add/edit/import/rebuild flows.

### Schema and metadata
- [ ] Add `lemmatized_search_text` to `poems`.
- [ ] Create `app_metadata`.
- [ ] Persist `schema_version`.
- [ ] Persist `search_index_version`.
- [ ] Persist `last_successful_full_rebuild_at`.
- [ ] Mark fresh V2 databases current immediately.
- [ ] Mark migrated V1 databases with a legacy/outdated search-index version.

### Tests
- [ ] Create `tests/test_lexical.py`.
- [ ] Create `tests/test_index_metadata.py`.
- [ ] Update repository tests for lexical derived data.
- [ ] Update CSV import tests for lexical derived data and partial-success preservation.
- [ ] Update CLI import tests for lexical derived data.
- [ ] Update rebuild tests for lexical regeneration and metadata behavior.
- [ ] Verify packaged local NLP resources exist and are used offline.

### Observable verification
- [ ] New and migrated databases contain `lemmatized_search_text`.
- [ ] Admin add/edit/import and CLI import persist non-empty lexical derived data.
- [ ] Manual rebuild refreshes lexical derived data for the full corpus.

---

## Task 010 — Automatic Startup Rebuild for Outdated Search Indexes

- [ ] **010** complete

### Source modules
- [ ] Create `src/poem_assoc/startup_upgrade.py`.
- [ ] Update `src/poem_assoc/app.py` to register and start the startup-upgrade coordinator.
- [ ] Update `src/poem_assoc/rebuild.py` with the status/result details needed by automatic rebuild.
- [ ] Update `src/poem_assoc/routes/public.py` to surface upgrade status and block search submissions while unavailable.
- [ ] Update `src/poem_assoc/routes/admin.py` to block admin writes during startup upgrade while keeping read-only visibility.

### Templates and styles
- [ ] Update `templates/search.html` with upgrade-in-progress and upgrade-failed states.
- [ ] Update `templates/admin/_base.html` with a persistent upgrade banner.
- [ ] Update `templates/admin/dashboard.html` so the explicit rebuild action is the retry path after failure.
- [ ] Update `static/css/styles.css` with upgrade status styles.

### Upgrade behavior
- [ ] Detect legacy/outdated `search_index_version` on startup.
- [ ] Launch automatic rebuild exactly once per process when required.
- [ ] Keep public search disabled while upgrade is running.
- [ ] Keep admin writes disabled while upgrade is running.
- [ ] Keep search disabled if startup rebuild fails.
- [ ] Refresh the in-memory search cache on successful startup rebuild.
- [ ] Update metadata to current only after success.

### Tests
- [ ] Create `tests/test_startup_upgrade.py`.
- [ ] Update public route tests for startup-upgrade availability states.
- [ ] Update admin dashboard tests for read-only visibility during upgrade.
- [ ] Update rebuild route gating tests for startup-upgrade blocking.
- [ ] Verify success, failure, retry, and no-op-current-version cases.

### Observable verification
- [ ] Old installs show `search data is being upgraded` on startup.
- [ ] Search/admin writes remain blocked until rebuild succeeds.
- [ ] Failure state is surfaced clearly and remains blocked until retry.

---

## Task 011 — Exact Lexical Matching and Combined Search Ranking

- [ ] **011** complete

### Scoring constants
- [ ] Centralize semantic weight.
- [ ] Centralize lexical weight.
- [ ] Centralize hard semantic floor.
- [ ] Centralize exact lexical match value.
- [ ] Centralize synonym lexical match value for later use.
- [ ] Centralize label thresholds and result limit.

### Search behavior
- [ ] Extend `lexical.py` with query-term building.
- [ ] Extend `search.py` to preload lexical match data in memory.
- [ ] Compute full-corpus `semantic_score`.
- [ ] Compute exact-only `lexical_score` across all meaningful query words.
- [ ] Average lexical evidence across multi-word queries.
- [ ] Zero lexical contribution below the semantic floor.
- [ ] Compute `final_score`.
- [ ] Sort by `final_score` descending and title ascending.
- [ ] Base relevance labels on `final_score`.

### Tests
- [ ] Create `tests/test_search_v2_exact.py`.
- [ ] Create `tests/fixtures/fixture_v2_exact.csv`.
- [ ] Update existing search service tests for combined-score ranking and labels.
- [ ] Update public route tests to confirm unchanged UI behavior with new ranking.
- [ ] Verify exact-match promotion, multi-word averaging, no stacking, and floor behavior.

### Observable verification
- [ ] Search ranking reflects exact lexical coverage plus semantic similarity.
- [ ] Search still returns exactly 5 results.
- [ ] Public UI stays unchanged.

---

## Task 012 — WordNet Synonym Expansion with Configurable Lexical Boost

- [ ] **012** complete

### Config and source modules
- [ ] Add `ENABLE_SYNONYM_EXPANSION` to config with default enabled.
- [ ] Create `src/poem_assoc/synonyms.py`.
- [ ] Extend `src/poem_assoc/lexical.py` with POS-tagged query terms.
- [ ] Update `src/poem_assoc/search.py` to apply synonym fallback scoring.
- [ ] Update `src/poem_assoc/app.py` to instantiate the synonym expander.

### Synonym rules
- [ ] Expand only nouns and adjectives.
- [ ] Use only the top 1 synset.
- [ ] Discard multi-word synonyms.
- [ ] Exclude the original query word from its synonym list.
- [ ] Exclude stopwords and invalid terms.
- [ ] Normalize and deduplicate after normalization.
- [ ] Cap surviving synonyms at 5 per eligible query word.
- [ ] Preserve exact-match precedence over synonym matches.

### Tests
- [ ] Create `tests/test_synonyms.py`.
- [ ] Create `tests/fixtures/fixture_v2_synonyms.csv`.
- [ ] Update search tests to cover synonym-only retrieval, config-flag rollback, and mixed exact/synonym multi-word queries.
- [ ] Verify verbs and adverbs are not synonym-expanded.
- [ ] Verify no-usable-synonyms fallback behavior.

### Observable verification
- [ ] Synonym-only poems can rank better when semantic similarity passes the floor.
- [ ] Setting `ENABLE_SYNONYM_EXPANSION=false` removes synonym boosts without removing exact lexical matching.
- [ ] Public UI still exposes no synonym-specific controls.

---

## Task 013 — Synonym Cache, Search Diagnostics, and V2 Regression Hardening

- [ ] **013** complete

### Config and runtime behavior
- [ ] Add local log-level configuration.
- [ ] Add process-lifetime synonym cache keyed by normalized eligible query word.
- [ ] Keep cache reset behavior tied to process restart only.
- [ ] Emit structured local diagnostics from the search path.

### Required logged fields
- [ ] Original query
- [ ] Normalized semantic query
- [ ] Lexical query words after stopword removal
- [ ] POS tags used for synonym eligibility
- [ ] Synonym expansions actually used
- [ ] Cache hit/miss status
- [ ] Per-result semantic score
- [ ] Per-result lexical score
- [ ] Per-result final score
- [ ] Per-result exact vs synonym match reason by query word
- [ ] Triggering synonym when a synonym match occurs

### Regression assets and tests
- [ ] Create `tests/fixtures/fixture_v2_regression.csv`.
- [ ] Create `tests/test_search_diagnostics.py`.
- [ ] Create `tests/test_v2_regression.py`.
- [ ] Extend startup-upgrade tests with final V2 acceptance coverage.
- [ ] Extend rebuild tests with regression-corpus lexical regeneration coverage.
- [ ] Verify deterministic search ordering for fixed fixture data.
- [ ] Verify cache hit on repeated eligible-word searches in the same process.
- [ ] Verify diagnostics remain local-only and omit full poem text.

### Observable verification
- [ ] Repeated searches reuse cached synonym expansions.
- [ ] Local logs contain the required diagnostics when enabled.
- [ ] Final V2 acceptance coverage exists for upgrade, ranking, and regeneration behavior.

---

## Cross-Cutting V2 Verification

- [ ] Every V2 requirement in the design document is mapped to at least one task.
- [ ] No V2 task includes out-of-scope functionality.
- [ ] No forward dependency exists in `009`–`013`.
- [ ] Each task leaves the system runnable by the end of the task.
- [ ] Each task produces an observable outcome.
- [ ] Each task remains a vertical slice rather than an isolated layer.
- [ ] No placeholder implementations or TODO-based scaffolding are required.
- [ ] Search stays fully offline on Windows after installation.
- [ ] Required local WordNet and NLTK resources are bundled.
- [ ] Existing installs automatically rebuild on first startup after upgrade.
- [ ] `lemmatized_search_text` is populated for all poems after upgrade and rebuild.
- [ ] Search still returns exactly 5 results.
- [ ] Ranking uses `0.8 * semantic + 0.2 * lexical`.
- [ ] Exact lexical matching applies to all non-stopword query words.
- [ ] Synonym expansion applies only to nouns and adjectives.
- [ ] Top-1 synset, single-word-only, max-5 synonym rules are enforced.
- [ ] Lexical boost is disabled below the semantic floor.
- [ ] Relevance labels use combined score thresholds.
- [ ] Synonym expansion can be disabled through configuration.
- [ ] Basic local logging and in-memory synonym caching exist.
- [ ] `pytest` passes with real SQLite, real filesystem fixture files, and local NLP resources.
