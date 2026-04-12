# Poetry Association Tool
## Design Document for Synonym-Aware Search
Version: 2.0  
Status: Approved for implementation  
Audience: Developer handoff  
Primary stakeholder: Private poet user  
Deployment target: Windows, local web app started manually and opened in a browser

---

## 1. Document purpose

This document defines the next version of the Poetry Association Tool. It extends the existing local, offline semantic poem search system with synonym-aware retrieval based on a local dictionary/thesaurus source.

The goal of this version is narrow and explicit:

**Improve recall for obvious synonym cases**, such as a query for `light` retrieving a poem that uses `illumination`.

This document is intended to be implementation-ready. It incorporates the existing Version 1 architecture and requirements as the baseline, then specifies all new and changed requirements for Version 2.

---

## 2. Product summary

The Poetry Association Tool is a private local search tool for a single poet user. It stores a curated poem collection and lets the user enter a single word or short phrase to retrieve the top 5 most associated poems.

Version 1 already supports:
1. Local semantic search using embeddings
2. Local SQLite storage
3. Modal poem viewing
4. Admin add, edit, delete, CSV import, and rebuild
5. Fully offline runtime behavior

Version 2 keeps that core design intact and adds a **second ranking signal**:
1. Existing semantic similarity remains the primary ranking signal
2. A new lexical synonym signal improves recall for clear synonym cases
3. The system remains fully offline
4. The user-facing UI remains simple and unchanged

---

## 3. Goals and non-goals

### 3.1 Goals

1. Improve recall for clear synonym matches
2. Preserve the current semantic-search behavior as the dominant signal
3. Keep the implementation deterministic, offline, and debuggable
4. Avoid broad exploratory or metaphor-heavy expansion in this version
5. Keep the end-user experience unchanged and implicit
6. Allow safe rollback through configuration without code changes

### 3.2 Non-goals for this version

1. No broad concept graph or exploratory related-word browsing
2. No user-facing explanation UI
3. No user-facing search modes or toggles
4. No phrase-level thesaurus expansion
5. No negation-aware semantic parsing
6. No custom synonym editor in the admin UI
7. No embedding-query expansion
8. No public cloud dependency or online dictionary lookups

---

## 4. High-level design decision summary

Version 2 will use a **hybrid ranking approach**.

1. **Semantic score**
   - Computed exactly from the original user query
   - Uses the existing embedding pipeline
   - Remains the dominant ranking factor

2. **Lexical score**
   - Computed from exact query-word matches and synonym matches
   - Uses local WordNet-based synonym expansion
   - Operates on stored lemmatized poem text

3. **Final score**
   - `0.8 * semantic_score + 0.2 * lexical_score`

4. **Scope of synonym use**
   - Apply WordNet only at query time
   - Do **not** modify stored poem embeddings with synonym expansion
   - Do **not** expand the embedding query text with synonyms

This keeps synonym logic isolated, tunable, and reversible.

---

## 5. Functional requirements

### 5.1 End-user search behavior

The main search experience remains intentionally simple.

1. The user enters a word or short phrase
2. Search returns exactly 5 results
3. Results are ranked using the new combined score
4. Clicking a result opens the poem in the existing modal
5. The user is not shown synonym expansions or internal scoring details
6. The feature is fully implicit

### 5.2 Unchanged public UI behavior

The following Version 1 behaviors remain unchanged:

1. Search is available without authentication
2. The query remains visible after search
3. Results persist until a new search is run
4. Pressing Enter triggers search
5. Empty or whitespace-only input does nothing
6. The modal preserves line breaks and includes Copy
7. Top-5 result count remains fixed
8. Tie-breaking remains alphabetical by title after score comparison

### 5.3 Admin behavior

No new end-user-facing synonym controls are required in this version.

Admin-facing behavior changes are limited to backend/indexing support.

1. Add, edit, delete, CSV import, and rebuild remain supported
2. Any write operation that changes poem content must regenerate all derived search data for that poem
3. A full rebuild must regenerate both existing embedding data and new synonym-related derived data
4. Basic logging must be added for tuning and debugging
5. No synonym management UI is required in this version

---

## 6. Dictionary and thesaurus source

### 6.1 Source choice

Use **local WordNet** as the synonym source.

1. It must be available fully offline
2. It must be bundled with the application
3. No runtime internet access is allowed
4. No external API calls are allowed for synonym lookup

### 6.2 Supporting NLP stack

Use the NLTK stack for synonym and lemmatization workflows.

1. Use NLTK with local WordNet data for synonym retrieval
2. Use NLTK lemmatization
3. Use the NLTK POS tagger for query word part-of-speech filtering
4. Bundle all required local NLTK resources with the application

### 6.3 Design rationale

This stack is preferred because it is:

1. Fully offline
2. Consistent across synonym lookup, POS handling, and lemmatization
3. Lightweight enough for the current local Windows deployment target
4. Easy for a single developer to implement and maintain

---

## 7. Query processing pipeline

The system now has two parallel paths:
1. The existing semantic embedding path
2. The new lexical synonym path

### 7.1 Query pipeline overview

For each search request:

1. Validate input as in Version 1
2. Compute the semantic score using the original normalized query only
3. Build the lexical query representation
4. Compute a lexical score for every poem
5. Combine semantic and lexical scores for every poem
6. Rank by combined score
7. Return the top 5 results

### 7.2 Semantic embedding path

The semantic path must remain unchanged except where explicitly noted.

1. Normalize the incoming query using the existing query normalization behavior
2. Generate a query embedding from the original normalized query only
3. Normalize the query embedding
4. Compare it to all stored normalized poem embeddings using cosine similarity
5. Use the resulting cosine value as `semantic_score`

### 7.3 Lexical path overview

The lexical path is new.

1. Tokenize the query into words
2. Remove standard stopwords for lexical processing
3. Normalize remaining query words using the same normalization pipeline used for stored lemmatized poem text
4. Allow **exact lexical matching** for all remaining non-stopword query words
5. Allow **synonym expansion** only for query words tagged as nouns or adjectives
6. Build per-word synonym sets
7. Match query words and synonyms against stored lemmatized poem text
8. Compute one lexical score per poem

### 7.4 Negation handling

Version 2 does **not** attempt special negation handling.

1. Queries like `not light` are processed normally
2. Negated words are not suppressed
3. No semantic inversion is attempted

This is explicitly acceptable for Version 2.

---

## 8. Query normalization and token handling

### 8.1 Existing normalization

The existing query normalization requirements remain in force for the semantic path.

1. Trim leading and trailing whitespace
2. Lowercase
3. Normalize basic punctuation
4. Apply other simple normalization steps that stabilize the query without materially changing meaning

### 8.2 Lexical tokenization

For the lexical path:

1. Tokenize the query into words
2. Remove standard stopwords
3. Preserve only meaningful query words for lexical scoring
4. Process all meaningful query words even for multi-word queries

### 8.3 Multi-word queries

For multi-word queries such as `quiet light` or `burning hope`:

1. Expand each meaningful query word independently
2. Do not attempt phrase-level thesaurus lookup
3. Do not collapse the query into a single concept
4. Compute lexical evidence per query word
5. Average per-word lexical evidence to get the poem’s lexical score

---

## 9. Part-of-speech filtering

### 9.1 POS restriction for synonym expansion

Synonym expansion applies only to **nouns and adjectives**.

1. Nouns are eligible for synonym expansion
2. Adjectives are eligible for synonym expansion
3. Verbs are not expanded in this version
4. Adverbs are not expanded in this version

### 9.2 Exact lexical matching scope

Exact lexical matching is broader than synonym expansion.

1. Exact lexical matching applies to **all non-stopword query words**
2. Exact matches are not restricted to nouns and adjectives
3. This allows exact query words to contribute lexical evidence even when they are not synonym-expanded

### 9.3 POS tagging implementation

1. Use the NLTK POS tagger
2. Map NLTK POS tags to the subset needed for WordNet lookup
3. If a word does not map cleanly to noun or adjective, it is not synonym-expanded
4. If POS tagging fails for a word, skip synonym expansion for that word and continue

---

## 10. Synonym expansion rules

### 10.1 When synonym expansion is used

1. Synonym expansion is applied to **all queries**
2. It is fully implicit to the user
3. It only affects the lexical signal
4. It does not affect the embedding query text
5. It does not alter stored poem embeddings

### 10.2 Sense handling

To keep the feature focused on obvious synonym cases:

1. Use only the **top 1 WordNet synset** for each eligible query word
2. Do not merge across multiple synsets in this version
3. This is intentionally conservative to reduce polysemy noise

### 10.3 Expansion size

1. Extract at most **5 synonyms per eligible query word**
2. This is a hard cap
3. The cap is applied after normalization and deduplication

### 10.4 Multi-word synonyms

1. Discard multi-word synonym entries from WordNet
2. Only single-word synonym candidates are used
3. Do not split multi-word entries into separate words
4. Do not attempt phrase matching for WordNet phrases

### 10.5 Duplicate handling

1. Deduplicate synonyms after normalization
2. Keep the first surviving occurrence
3. Variants that normalize to the same lemma count as duplicates

### 10.6 Words with no usable synonyms

1. If WordNet returns no usable synonym set for a word, continue without synonym expansion for that word
2. Search still proceeds normally
3. The system falls back to embedding-only behavior plus any exact lexical matches for other query words

### 10.7 Recommended exclusion rules

During synonym extraction, exclude:

1. The original query word itself from the synonym list
2. Stopwords
3. Multi-word terms
4. Empty or invalid terms after normalization

---

## 11. Lemmatization and lexical search index

### 11.1 Core design

Lexical matching must operate on **lemmatized text**.

1. Store a persisted lemmatized representation for each poem
2. Normalize query words and synonyms with the same pipeline
3. Match only in normalized lemmatized space

### 11.2 Where lemmatization is applied

Lemmatization is applied at both indexing and query time.

1. At indexing time, generate and store lemmatized poem text
2. At query time, normalize and lemmatize all lexical query words and synonyms
3. Match the normalized lexical terms against stored lemmatized poem text

### 11.3 Storage format

Persist a new derived text field for lexical matching.

Recommended field:
- `lemmatized_search_text`

Definition:
- A normalized, lemmatized representation of the searchable poem content

Recommended content:
- Title and poem body together in one searchable normalized field, because title and body have equal lexical weight in this version

### 11.4 Matching scope

1. Lexical matching must consider both title and poem body
2. Title and body have equal lexical weight
3. No separate title boost or body boost is required
4. Matching must operate only on the lemmatized representation

### 11.5 Repeated occurrences

Repeated occurrences do not increase lexical score.

1. Multiple hits for the same query word do not stack
2. Multiple different synonyms for the same query word do not stack
3. The score per query word is capped at its best available match class

This avoids long-poem bias.

---

## 12. Scoring model

### 12.1 Semantic score

`semantic_score = cosine_similarity(query_embedding, poem_embedding)`

Notes:
1. Use the existing normalized-embedding cosine flow
2. Use the original query only
3. Do not augment the embedding query with synonyms

### 12.2 Per-query-word lexical scoring

For each meaningful query word, determine one lexical contribution for a given poem:

1. **Exact match**: `1.0`
2. **Synonym match**: `0.7`
3. **No match**: `0.0`

Rules:
1. Exact match takes precedence over synonym match
2. For any one query word, use only the strongest applicable match
3. Do not sum multiple synonym hits for the same query word
4. Do not count frequency

### 12.3 Multi-word lexical aggregation

For a multi-word query:

1. Score each meaningful query word independently
2. Compute the poem’s `lexical_score` as the arithmetic average of the per-word lexical scores
3. This rewards coverage across more of the query while avoiding strong long-text bias

Example:
- Query: `quiet light`
- Poem exact-matches `quiet` and synonym-matches `illumination`
- Per-word scores: `1.0` and `0.7`
- `lexical_score = 0.85`

### 12.4 Hard semantic floor for lexical boost

Lexical evidence must not override clearly unrelated semantic matches.

Rule:
1. If `semantic_score < 0.20`, then set effective lexical contribution to `0.0`

Equivalent implementation:
1. If `semantic_score < 0.20`, use `lexical_score = 0.0` for final scoring
2. Otherwise, use the computed lexical score normally

### 12.5 Final combined score

`final_score = 0.8 * semantic_score + 0.2 * lexical_score`

Notes:
1. Combined scoring is computed for the **full corpus**
2. Do not use embedding-first candidate reranking only
3. Do not treat lexical score as a tie-breaker only
4. Rank globally by `final_score`

### 12.6 Tie-breaking

1. Sort by descending `final_score`
2. Break ties alphabetically by title
3. Empty titles should still display as `Untitled`, as in Version 1

---

## 13. Relevance labels

### 13.1 Label basis

In Version 2, relevance labels must be based on the **combined score**, not embedding-only score.

### 13.2 Thresholds

Keep the same numeric thresholds used previously, but apply them to `final_score`.

1. **Strong match**: `final_score >= 0.45`
2. **Moderate match**: `final_score >= 0.30 and < 0.45`
3. **Weak match**: `final_score < 0.30`

### 13.3 Consequence

This keeps labeling internally consistent with ranking while preserving the existing threshold values.

---

## 14. Retrieval flow

### 14.1 Corpus-wide scoring

Combined scoring must be applied across the entire poem corpus.

1. Compute semantic and lexical scores for every poem
2. Compute `final_score` for every poem
3. Sort the full corpus by `final_score`
4. Return the top 5 poems

### 14.2 Rationale

This is required because:

1. The corpus is small
2. Full-corpus scoring is computationally feasible
3. Embedding-first candidate reranking could miss valid synonym-driven improvements
4. The logic is simpler and easier to reason about

---

## 15. Data model changes

### 15.1 Existing fields

The existing poem data model remains in place.

Recommended existing fields:
1. `id`
2. `title`
3. `text`
4. `cleaned_text`
5. `embedding`
6. `created_at`
7. `updated_at`

### 15.2 New field

Add:

1. `lemmatized_search_text`

Purpose:
1. Persist normalized lemmatized text for lexical exact and synonym matching

### 15.3 Metadata and versioning

Add application-level metadata sufficient to detect index/schema compatibility.

Recommended metadata concepts:
1. database schema version
2. search index version
3. last successful full rebuild timestamp

This can be implemented in:
1. a metadata table
2. a config table
3. an equivalent persistent versioning mechanism

---

## 16. Indexing and derived-data lifecycle

### 16.1 On add

When a poem is added:

1. Validate as in Version 1
2. Generate `cleaned_text`
3. Generate `lemmatized_search_text`
4. Generate embedding
5. Save only if all required derived data succeeds

### 16.2 On edit

When a poem is edited:

1. Recompute `cleaned_text`
2. Recompute `lemmatized_search_text`
3. Recompute embedding
4. Save only if all required derived data succeeds

### 16.3 On CSV import

For each imported poem:

1. Validate row as in Version 1
2. Generate `cleaned_text`
3. Generate `lemmatized_search_text`
4. Generate embedding
5. Save only if the row succeeds
6. Preserve partial success behavior exactly as in Version 1

### 16.4 On full rebuild

A full rebuild must regenerate all derived search data.

1. Recompute embeddings
2. Recompute `lemmatized_search_text`
3. Refresh any in-memory search data structures or caches
4. Update search index version metadata when successful

---

## 17. Upgrade and migration behavior

### 17.1 Migration requirement

The system is already implemented, so Version 2 must support upgrade of existing installations.

### 17.2 Upgrade behavior

On first startup after upgrading to Version 2:

1. Detect that the installed search/index version is older than the current application version
2. Automatically start a **full rebuild**
3. Regenerate all derived search data for all poems
4. Do not require a manual admin migration step

### 17.3 Runtime behavior during startup rebuild

During the automatic upgrade rebuild:

1. Search must be disabled
2. Admin write operations must be disabled
3. The application should show a simple status message indicating that search data is being upgraded
4. After successful rebuild, the app should return to normal operation

### 17.4 Failure handling

If automatic upgrade rebuild fails:

1. The application must surface a clear error
2. The system must not silently operate with mixed old and new index formats
3. A retry path must exist, either through restart or explicit rebuild command

---

## 18. Configuration

### 18.1 Feature flag

Synonym expansion must be globally configurable.

1. Provide a global config flag
2. Default it to enabled
3. Allow it to be disabled without code changes

Recommended config name:
- `ENABLE_SYNONYM_EXPANSION=true`

### 18.2 Required tunable constants

Keep the following values centralized and easy to adjust:

1. semantic weight: `0.8`
2. lexical weight: `0.2`
3. semantic floor for lexical boost: `0.20`
4. exact lexical match value: `1.0`
5. synonym lexical match value: `0.7`
6. strong label threshold: `0.45`
7. moderate label threshold: `0.30`
8. max synonyms per eligible query word: `5`

### 18.3 Additional recommended config points

1. stopword list location or definition
2. NLTK/WordNet resource path
3. logging level
4. cache size policy or simple on/off
5. search index version constant

---

## 19. Caching

### 19.1 Query-time synonym cache

Use an **in-memory cache** for synonym expansions.

1. Cache normalized eligible query words to their processed synonym sets
2. Cache only query-time expansion artifacts
3. No persistent synonym cache is required

### 19.2 Cache scope

The cache may store:
1. POS result for eligible words
2. resolved top synset selection
3. final normalized synonym set

### 19.3 Cache invalidation

1. Cache lifetime may be application-process lifetime
2. A full rebuild does not require a persistent cache reset because the cache is in-memory only
3. Application restart resets the cache

---

## 20. Logging and diagnostics

### 20.1 Logging level

Provide **basic backend logging only**. No debug UI is required.

### 20.2 Required logged information

For each search request, log enough data to tune and debug synonym behavior.

Recommended structured fields:
1. original query
2. normalized semantic query
3. lexical query words after stopword removal
4. POS tags used for eligible expansion words
5. synonym expansions actually used
6. cache hit or miss for synonym lookups
7. per-result semantic score
8. per-result lexical score
9. per-result final score
10. for each matched result, which query word matched and whether it was:
    1. exact query-word match
    2. synonym match
11. if synonym match occurred, which specific synonym triggered the match

### 20.3 Logging constraints

1. Keep logs local
2. No analytics service or remote telemetry
3. Logging must be optional or level-controlled so the private local tool remains simple

---

## 21. Performance and runtime considerations

### 21.1 Expected scale

The current poem collection size is small enough that full-corpus combined scoring is acceptable.

### 21.2 Recommended in-memory structures

At startup, it is reasonable to preload:
1. poem IDs
2. titles
3. embeddings
4. lemmatized search text

This is recommended, not mandatory, but likely beneficial at the current scale.

### 21.3 Search-time computation

Per search:
1. compute one query embedding
2. prepare lexical query artifacts
3. scan all poems for lexical evidence
4. compute combined score for all poems
5. sort and return top 5

This is acceptable for the current collection size.

---

## 22. Offline packaging and deployment

### 22.1 Offline-first requirement

Version 2 must preserve the existing offline requirement.

1. No internet access at runtime
2. No first-run downloads
3. No cloud dependency for synonym or NLP resources

### 22.2 Packaging requirement

Bundle the necessary NLP resources with the application.

This includes:
1. local WordNet data
2. local NLTK lemmatization resources
3. local POS tagging resources
4. any other required static NLP assets

### 22.3 Deployment behavior

The app must continue to be:
1. Windows-first
2. manually started by the user
3. opened in a browser
4. self-contained for offline usage after installation

---

## 23. Search algorithm specification

This section is normative.

### 23.1 Definitions

Let:
1. `Q_raw` = original user query
2. `Q_sem` = normalized query used for embedding
3. `Q_terms` = normalized non-stopword query words used for lexical scoring
4. `Q_expandable_terms` = subset of `Q_terms` tagged as noun or adjective
5. `Syn(term)` = normalized synonym set for `term` from top 1 WordNet synset, single-word only, deduped, max 5
6. `P_lemma` = poem’s stored `lemmatized_search_text`

### 23.2 Per-word lexical score

For each `term` in `Q_terms`, define `word_score(term, poem)` as:

1. `1.0` if `term` is found in `P_lemma`
2. else `0.7` if `term` is in `Q_expandable_terms` and any synonym in `Syn(term)` is found in `P_lemma`
3. else `0.0`

### 23.3 Poem lexical score

If `Q_terms` is empty:
1. set `lexical_score = 0.0`

Otherwise:
1. `lexical_score = average(word_score(term, poem) for all term in Q_terms)`

### 23.4 Hard floor

If `semantic_score < 0.20`:
1. override `lexical_score = 0.0`

### 23.5 Final score

1. `final_score = 0.8 * semantic_score + 0.2 * lexical_score`

### 23.6 Ranking

1. Sort all poems by descending `final_score`
2. Break ties alphabetically by title
3. Return top 5

---

## 24. Testing requirements

### 24.1 Testing scope

This version requires automated tests for the new synonym-aware behavior.

### 24.2 Minimum required test coverage

1. Query tokenization and stopword removal for lexical processing
2. POS filtering so only nouns and adjectives are synonym-expanded
3. WordNet synonym extraction:
   1. top 1 synset only
   2. single-word only
   3. cap at 5
   4. deduplication after normalization
4. Lemmatization consistency between indexing and query-time normalization
5. Exact lexical match scoring equals `1.0`
6. Synonym lexical match scoring equals `0.7`
7. Exact match precedence over synonym match
8. No stacking from repeated occurrences
9. Multi-word query lexical averaging behavior
10. Hard semantic floor at `0.20`
11. Combined score formula
12. Relevance label assignment from combined score
13. Fallback behavior when a word has no usable synonyms
14. Global config flag disabling synonym expansion
15. In-memory cache basic behavior
16. Automatic rebuild on first startup after upgrade
17. Add, edit, CSV import, and rebuild regeneration of `lemmatized_search_text`

### 24.3 Recommended integration tests

1. A query such as `light` retrieves a poem containing `illumination` more reliably than under embedding-only scoring
2. A poem with only weak semantic similarity but a synonym hit below the `0.20` floor does not receive lexical boost
3. A multi-word query rewards poems that cover more of the query
4. Search results remain deterministic for fixed test data

### 24.4 Regression fixture recommendation

Create a small deterministic fixture corpus with:
1. exact-match cases
2. synonym-only cases
3. ambiguous-word cases
4. low-semantic-similarity false-positive traps
5. multi-word query cases

This will make future tuning safer.

---

## 25. Acceptance criteria for Version 2

Implementation is acceptable when all of the following are true:

1. The app still runs fully offline on Windows
2. WordNet and required NLP resources are bundled locally
3. Existing installations automatically trigger a full rebuild on first startup after upgrade
4. A new stored lemmatized poem field exists and is populated for all poems
5. Search still returns exactly 5 results
6. Search ranking uses `0.8 * semantic + 0.2 * lexical`
7. Embedding score uses the original query only
8. Synonym expansion affects only the lexical signal
9. Exact lexical matching applies to all non-stopword query words
10. Synonym expansion applies only to nouns and adjectives
11. Only the top 1 synset is used per eligible query word
12. Only single-word synonyms are used
13. A maximum of 5 synonyms per eligible query word is applied
14. Lexical scoring uses:
    1. exact match = `1.0`
    2. synonym match = `0.7`
    3. no match = `0.0`
15. Multi-word query lexical score is computed by averaging per-word best matches
16. Lexical boost is disabled when semantic similarity is below `0.20`
17. Relevance labels use combined score thresholds:
    1. Strong `>= 0.45`
    2. Moderate `>= 0.30 and < 0.45`
    3. Weak `< 0.30`
18. The feature can be disabled through a global config flag
19. Basic local logging exists for query expansion and score inspection
20. Automated tests cover the new lexical and upgrade behavior

---

## 26. Recommended implementation notes

These are recommendations, not additional requirements.

1. Keep the semantic and lexical pipelines cleanly separated in code
2. Centralize all scoring constants in one module
3. Implement lexical matching using token-set membership or equivalent efficient lookup on `lemmatized_search_text`
4. Keep the query-time synonym expansion API deterministic and side-effect free
5. Use structured logs rather than free-form strings where practical
6. Maintain explicit search/index version metadata to support future migrations
7. Treat the automatic upgrade rebuild as an index migration, not as optional maintenance

---

## 27. Future work

The following items are intentionally out of scope for Version 2 but are strong candidates for future versions.

### 27.1 Synonym quality control

1. Admin-managed synonym blacklist
2. Admin-managed synonym override list
3. Custom poet-specific synonym dictionary layered over WordNet
4. Per-word suppression of bad WordNet expansions

### 27.2 Explainability and debugging

1. Admin debug panel showing:
   1. expanded synonyms
   2. exact or synonym trigger per result
   3. semantic, lexical, and final score breakdown
2. Why-this-matched explanation in the result UI
3. Matched-line or matched-term display

### 27.3 Search-quality tuning

1. Curated regression dataset based on real user queries
2. Adjustable scoring weights from config or admin UI
3. Alternative label thresholds tuned from production-style evaluation
4. Optional candidate-set reranking strategies if corpus size later grows
5. More sophisticated polysemy handling

### 27.4 NLP sophistication

1. Phrase-level synonym handling
2. Verb expansion
3. Adverb expansion
4. Negation-aware query handling
5. Context-aware sense disambiguation
6. Optional embedding-query expansion behind config

### 27.5 User-facing controls

1. Optional “include related words” toggle
2. Search modes such as strict, balanced, and expanded
3. Transparent display of related words used in search

---

## 28. Final implementation summary

Build Version 2 as a conservative synonym-aware extension of the existing Poetry Association Tool.

Keep the current embedding-based search as the primary signal. Add a second lexical signal based on local WordNet synonym expansion and lemmatized exact-word matching. Use exact-match precedence, noun/adjective-only synonym expansion, top-1-synset conservative selection, a 5-synonym cap, and an 80/20 semantic-to-lexical weighting. Apply combined scoring across the full corpus, preserve the offline local architecture, automatically rebuild on upgrade, bundle all NLP assets locally, and expose no new end-user UI complexity in this version.
