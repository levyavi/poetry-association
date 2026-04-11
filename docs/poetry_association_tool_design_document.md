# Poetry Association Tool
## Design Document

Version: 1.0  
Status: Approved for implementation  
Audience: Developer handoff  
Primary stakeholder: Private poet user  
Deployment target for Version 1: Windows, local web app started manually and opened in a browser

---

## 1. Product summary

This product is a private poetry search tool for a single poet user. The system stores a curated poem collection and lets a user enter a single word or short phrase to retrieve the top 5 poems most semantically associated with that query.

The tool is intended for immediate use by one poet friend. It should be designed so it can later be expanded toward broader public use, but Version 1 is a private, minimal, offline-first tool.

The system must work fully offline at runtime, including first launch. The embedding model must already be packaged or installed beforehand. No external API calls or internet access are permitted for search, ranking, or administration.

---

## 2. Product goals

### 2.1 Goals

1. Provide a very simple search experience for poem association.
2. Return the top 5 most semantically related poems for a word or short phrase.
3. Let the user click a result and read the full poem in a modal.
4. Let an admin add, edit, delete, and import poems.
5. Keep the system fully local and offline.
6. Keep the implementation simple enough for a single developer to build and maintain.

### 2.2 Non-goals for Version 1

1. No public user accounts.
2. No analytics or activity logging.
3. No advanced poem formatting beyond plain text with preserved line breaks.
4. No semantic highlighting, keyword highlighting, or matched-line explanation.
5. No recommendations beyond the search results.
6. No backup, export, or restore features.
7. No API integrations or cloud dependencies.
8. No keyboard navigation of results beyond pressing Enter to search.

---

## 3. Target users and usage context

### 3.1 Current target user

A private poet user who wants to search their collection by semantic association.

### 3.2 Future expansion consideration

The system should be structured so it can later be adapted for broader or public use, but Version 1 should optimize for simplicity, local use, and ease of handoff.

---

## 4. Scope of Version 1

Version 1 includes:

1. Public search page with no authentication.
2. Admin page protected by a password.
3. Local poem storage.
4. Local embedding generation and similarity search.
5. Manual poem add, edit, and delete.
6. CSV import.
7. Manual full embedding rebuild.
8. Fixed top-5 result retrieval.
9. Modal poem display.
10. Copy button for full poem text.

---

## 5. Required technology stack

The stack is fixed for Version 1.

1. Backend language: Python
2. Backend model: synchronous
3. Database: SQLite
4. Embedding model: local English embedding model, exact model specified below
5. Embedding model name: `all-MiniLM-L6-v2`
6. Web UI: minimal server-rendered web UI
7. Deployment form: local web app started manually by the user, then opened in a browser

### 5.1 Exact embedding model

Use:

`all-MiniLM-L6-v2`

Reasoning:

1. Small and fast
2. Suitable for approximately 330 poems
3. Good fit for local Windows use
4. Widely used and simple to integrate

### 5.2 Offline requirement

1. The app must work with no internet access at all, including first launch.
2. The embedding model must already be packaged or installed beforehand.
3. Search, import, and admin actions must not rely on network calls.

---

## 6. Functional requirements

### 6.1 User search experience

The main search interface must be accessible without authentication.

#### 6.1.1 Search input behavior

1. The user can enter a single word or a short phrase.
2. The input remains populated and editable after a search.
3. Pressing Enter triggers search.
4. The cursor should autofocus in the search input when the page loads.
5. If the user submits an empty or whitespace-only search, the system does nothing.
6. The query resets on page refresh.
7. No caching is required. Every query is computed fresh.
8. No debounce or rate limiting is required.

#### 6.1.2 Search output behavior

1. The system must always return exactly 5 results.
2. Results are returned as a single unified list.
3. Results are ordered primarily by semantic similarity score.
4. Ties are broken alphabetically by title.
5. Every result must display a relevance label.
6. The current query must be displayed above the results, for example: `Results for: "quiet grief"`.
7. Search results persist until the user performs a new search.
8. No additional low-relevance warning message is shown. Labels alone communicate relevance quality.

#### 6.1.3 Relevance labels

Use fixed thresholds, not relative per-query thresholds.

Initial default thresholds to implement and validate:

1. Strong match: cosine similarity >= 0.45
2. Moderate match: cosine similarity >= 0.30 and < 0.45
3. Weak match: cosine similarity < 0.30

These are proposed defaults and should be easy to adjust in configuration or constants during implementation if testing shows they need calibration.

#### 6.1.4 Result click behavior

1. Clicking a result opens the poem in a modal overlay.
2. The results remain visible in the background.
3. Closing the modal returns the user to the same results state.
4. The poem modal must include a Copy button.

#### 6.1.5 Poem display

1. Display plain text only.
2. Preserve original line breaks.
3. Do not include author.
4. No highlighting of matched lines or terms.
5. If a poem title is empty, display `Untitled` in the results and modal header.

### 6.2 Admin capabilities

The admin interface must be a separate page within the same web app.

#### 6.2.1 Admin authentication

1. The admin page is password-protected.
2. The main search page is open and does not require authentication.
3. The password must be configurable without changing code, for example via environment variable or config file.
4. After login, the admin remains logged in via a simple session until logout or browser close.
5. Persistent login across browser restarts is not required.

#### 6.2.2 Admin actions

The admin must be able to:

1. Add a poem manually
2. Edit an existing poem
3. Delete a poem
4. Import poems from CSV
5. Trigger a full embedding rebuild

#### 6.2.3 Admin feedback

1. Show minimal confirmation messages for successful actions, for example `Saved` or `Deleted`.
2. Show detailed error messages for failures.
3. Show loading indicators for admin operations.

#### 6.2.4 Delete safety

Deleting a poem must require an explicit confirmation prompt.

#### 6.2.5 Admin listing behavior

1. No search or filtering is required in the admin list.
2. Sorting options must be available.
3. Default sort order is Title, A to Z.

Supported sort options:

1. Title, A to Z
2. Title, Z to A
3. Creation time, newest first
4. Creation time, oldest first
5. Last modified, newest first
6. Last modified, oldest first

### 6.3 CSV import

#### 6.3.1 Supported format

CSV import must use a strict format:

1. UTF-8 encoding
2. Comma-delimited
3. Header row required
4. Exact required columns: `title` and `text`

No alternative header names or delimiter formats are required.

#### 6.3.2 Import behavior

1. Show a simple confirmation before import with the number of rows to import and the number of rows to skip as duplicates.
2. Admin can cancel an ongoing import.
3. If import is cancelled, keep rows already imported and stop further processing.
4. If import fails on a later row after some rows were imported, keep already imported rows and stop with an error.
5. No explicit import file size limit is required.

#### 6.3.3 Duplicate detection during CSV import

1. Duplicate detection is based on poem text, not title.
2. Duplicate detection compares cleaned text after normalization.
3. Duplicate detection remains strict and case-sensitive after cleaning.
4. Cleaning should include whitespace and formatting normalization, but should not lowercase or otherwise alter case for duplicate detection.

#### 6.3.4 CSV validation

1. No upfront validation pass is required.
2. The system attempts import directly and fails on errors.
3. Detailed error messages must be shown to the admin.

### 6.4 Manual add and edit rules

1. Poem text is required and must be non-empty.
2. Titles may be empty.
3. Titles may be duplicated.
4. Manual add and edit must not allow saving a poem whose cleaned text is identical to an existing poem.
5. If the title is edited, the embedding must be regenerated, because the title is part of the embedding input.

### 6.5 Rebuild behavior

1. A `Rebuild all embeddings` button must exist in the admin UI.
2. Search must be disabled while a full rebuild is in progress.
3. All admin write actions must be disabled while a full rebuild is in progress.
4. Admin write actions that must be disabled during rebuild include add, edit, delete, and CSV import.

---

## 7. Search and ranking design

### 7.1 Search method

Use local embedding-based semantic search.

#### 7.1.1 Ranking flow

1. Normalize the incoming search input.
2. Generate a query embedding.
3. Normalize the query embedding.
4. Compare it to all stored normalized poem embeddings using cosine similarity.
5. Sort by descending similarity score.
6. Break ties alphabetically by title.
7. Return the top 5 matches.

### 7.2 Input normalization

Search input should use advanced normalization before embedding.

Required normalization:

1. Trim leading and trailing whitespace
2. Lowercase the query
3. Handle basic punctuation normalization
4. Apply other simple normalization steps appropriate for stable query embedding, so long as they do not materially change meaning

### 7.3 Duplicate handling in search results

Near-duplicate or duplicate poems are allowed to appear naturally in the top 5 if they rank there. No deduplication or diversity post-processing is required in Version 1.

---

## 8. Data model

Use SQLite as the single local database.

### 8.1 Core poem record

Recommended schema fields:

1. `id` - primary key
2. `title` - text, nullable or empty string allowed
3. `text` - text, required
4. `cleaned_text` - cleaned canonical text used for duplicate comparison
5. `embedding` - binary or serialized vector data
6. `created_at` - timestamp
7. `updated_at` - timestamp

### 8.2 Notes on storage

1. Full poem text must be stored in the database.
2. The full poem must be retrievable by ID for display in the modal.
3. Embeddings should be stored persistently, not recomputed on each search.
4. Titles are part of the semantic representation and therefore part of the embedding input.

### 8.3 Embedding input format

Embedding input should combine title and poem text.

Recommended format:

`Title. Full poem text`

If title is empty, use only the poem text.

---

## 9. Text cleaning rules

Text cleaning is applied on input before storage and duplicate comparison.

Required cleaning behavior:

1. Trim leading and trailing whitespace
2. Normalize line endings
3. Collapse excessive blank lines
4. Clean obvious extra spacing where reasonable

Important constraint:

1. Do not lowercase poem text for storage
2. Do not remove meaningful poem structure
3. Preserve line breaks for display
4. Preserve case in stored poem text

---

## 10. Embedding lifecycle

### 10.1 When to generate embeddings

1. Generate on poem add
2. Generate on poem edit
3. Regenerate all on manual rebuild
4. Do not regenerate periodically

### 10.2 Failure handling

If embedding generation fails during add or edit:

1. Reject the operation
2. Show an error
3. Do not save the poem

### 10.3 Normalization approach

Use the following approach:

1. Normalize stored poem embeddings when created or rebuilt
2. Normalize each query embedding at search time

This is required for consistent cosine similarity behavior.

### 10.4 Model loading

1. Load the embedding model once at application startup
2. Reuse it for all requests
3. Do not load it per request

---

## 11. UI requirements

### 11.1 General UI principles

1. Minimal UI
2. Desktop and mobile responsive
3. Desktop and mobile should both work well in Version 1
4. Basic hover highlight on search results
5. No advanced interaction states required beyond basic hover and click behavior

### 11.2 Main search page

Must include:

1. Search input
2. Query context line, for example `Results for: "..."`
3. List of 5 results
4. Relevance label on each result
5. Modal poem viewer
6. Copy button in modal
7. Loading indicator during search

### 11.3 Admin page

Must include:

1. Login gate for admin password
2. Manual add form
3. Edit form
4. Delete action with confirmation
5. CSV import control
6. Simple pre-import confirmation counts
7. Rebuild all embeddings button
8. Sort controls for poem list
9. Loading indicators for admin operations
10. Minimal success messages and detailed error messages

---

## 12. Concurrency and runtime behavior

### 12.1 Concurrency support

The system should support concurrent access when deployed on a server, even though Version 1 uses a synchronous backend.

### 12.2 Rebuild lock behavior

During a full embedding rebuild:

1. User search must be disabled
2. Admin write operations must be disabled
3. Read-only admin viewing may remain available if convenient, but no writes are allowed

### 12.3 Import and write behavior

Version 1 can use simple application-level locking or route-level safeguards to prevent conflicting writes during rebuild.

---

## 13. Security requirements

Version 1 requires only basic security appropriate for a private tool.

1. Admin page must be password-protected.
2. Password must not be hardcoded in source control.
3. Password must be configurable through environment variable or config file.
4. Use standard session-based authentication for admin session state.
5. The public search page remains unauthenticated.
6. No user accounts or roles beyond admin are required.

---

## 14. Deployment requirements

### 14.1 Primary Version 1 deployment target

1. Windows only
2. Local web app
3. Started manually by the user
4. Opened in a browser

### 14.2 Architecture portability requirement

The implementation should be structured so it can later support either:

1. Local deployment
2. Hosted private deployment

This should require minimal architectural changes.

### 14.3 Health checks and monitoring

No monitoring or health check endpoint is required in Version 1.

---

## 15. Testing requirements

Include basic automated tests for core functions.

Minimum required automated test coverage:

1. Text cleaning behavior
2. Duplicate detection logic
3. Embedding generation pipeline integration at a basic level
4. Search ranking behavior for deterministic sample data
5. Tie-breaking by title
6. Add and edit rejection when duplicate cleaned text already exists
7. CSV import partial success behavior
8. Rebuild lock behavior at a basic level if practical

---

## 16. API and route suggestions

The exact route structure can be adjusted by the developer, but the following is a recommended starting point.

### 16.1 Public routes

1. `GET /` - search page
2. `POST /search` - submit query and return top 5 results
3. `GET /poems/<id>` - fetch full poem for modal display if using progressive loading

### 16.2 Admin routes

1. `GET /admin/login` - login page
2. `POST /admin/login` - submit password
3. `POST /admin/logout` - logout
4. `GET /admin` - admin page
5. `POST /admin/poems` - add poem
6. `POST /admin/poems/<id>/edit` - edit poem
7. `POST /admin/poems/<id>/delete` - delete poem
8. `POST /admin/import` - CSV import
9. `POST /admin/rebuild` - rebuild all embeddings

These routes are recommendations, not mandatory public API commitments.

---

## 17. Acceptance criteria

The implementation is acceptable when all of the following are true:

1. The app runs locally on Windows with no internet connection.
2. The embedding model is available locally and does not require download at runtime.
3. A user can enter a word or short phrase and get exactly 5 results.
4. Every result shows a relevance label.
5. Clicking a result opens the full poem in a modal.
6. The modal preserves line breaks and offers a Copy button.
7. The admin can add, edit, delete, and import poems from strict CSV format.
8. Empty titles are shown as `Untitled`.
9. Duplicate poem text is blocked for manual add and edit after cleaning.
10. CSV import skips duplicates based on cleaned, case-sensitive text comparison.
11. Partial CSV imports are preserved if a later row fails.
12. Partial CSV imports are preserved if the import is cancelled.
13. Rebuild all embeddings is available from the admin UI.
14. Search and admin write operations are disabled during rebuild.
15. Basic automated tests exist for core search and data logic.

---

## 18. Future work

The following items were explicitly identified as useful future possibilities but are out of scope for Version 1 unless re-prioritized later.

### 18.1 Search and ranking enhancements

1. Why-this-matched explanation for each result
2. Search by mood, theme, or image in addition to word and phrase
3. Multiple ranking modes, such as semantic, exact match, and hybrid
4. Semantic highlighting of related lines or segments
5. Keyword highlighting
6. Better relevance calibration tools
7. Near-duplicate suppression or diversity ranking
8. Adjustable result count

### 18.2 Metadata and curation

1. Tags such as theme, tone, era, or other admin metadata
2. Author field support
3. Notes field for admin-only commentary
4. Structured filtering and browsing

### 18.3 Discovery features

1. Random discovery mode
2. Exploratory browsing interface
3. Thematic collections or clusters
4. Similar-poem suggestions from a currently opened poem

### 18.4 User features

1. Save favorite poems
2. Search history
3. Recent poems viewed
4. Better keyboard accessibility and navigation
5. Richer poem formatting support

### 18.5 Language and model expansion

1. Hebrew support
2. Multilingual query support
3. Configurable model selection
4. Better poetry-specific models if later needed

### 18.6 Admin and operational improvements

1. Backup and restore
2. Export to CSV or JSON
3. Import preview with row-level validation
4. Admin search in poem list
5. Undo support for delete or edit
6. Logging of queries and clicks
7. Health checks and monitoring
8. Packaged desktop installer for non-technical users
9. Hosted deployment hardening for broader use

---

## 19. Recommended implementation notes for the developer

These notes are not strict requirements, but they align closely with the approved product decisions.

1. Use SQLite with a uniqueness check on cleaned text at the application layer, not title.
2. Store embeddings in a compact serialized binary form.
3. Preload all poem embeddings into memory after startup if convenient, given the small collection size.
4. Keep rebuild, import, and write locks simple and explicit.
5. Build the UI with minimal JavaScript. The requirements do not justify a frontend framework.
6. Make relevance thresholds easy to adjust in one place.
7. Keep search and admin concerns separated cleanly so future hosted deployment is easier.

---

## 20. Final implementation summary

Build a Python, SQLite, synchronous local web application for Windows that stores full poems, generates local embeddings with `all-MiniLM-L6-v2`, and returns the top 5 semantically associated poems for a word or short phrase. Provide an open search interface and a password-protected admin interface with add, edit, delete, CSV import, and rebuild capabilities. Keep the app fully offline, minimal, responsive, and simple to operate.
