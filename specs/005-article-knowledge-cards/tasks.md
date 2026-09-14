# Tasks: Structured Wiki Pages for Academic Papers and Articles

**Input**: Design documents from `/specs/005-article-knowledge-cards/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create source directories and install the single new dependency.

- [x] T001 Create source directories `data/raw/articles/` and `data/raw/papers/` (keep `.gitkeep` placeholder in each)
- [x] T00x Install pymupdf dependency by running `uv add pymupdf`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and model changes that every user story depends on. Must be complete before any US work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T00x Add `note_type TEXT` column to the `notes` table in `src/db.py` — add `ALTER TABLE notes ADD COLUMN note_type TEXT` inside `_init_db()` wrapped in a `try/except` that ignores "duplicate column name" errors; also add `CREATE INDEX IF NOT EXISTS idx_notes_note_type ON notes(note_type)` the same way
- [x] T00x Add `note_type: Optional[str] = None` field to the `NoteRecord` dataclass in `src/models.py` (after `word_count`)
- [x] T00x Update `db.py` `upsert_note()` to write `note_type` into the INSERT/UPDATE statement, and update `_row_to_note()` to read `note_type` from the row (depends on T003, T004)
- [x] T00x Add `note_type: Optional[str] = None` parameter to `get_pending_proposals()` in `src/db.py`; when set, append `AND n.note_type = ?` to the WHERE clause (depends on T003)

**Checkpoint**: Schema migration applies on next DB connection; `NoteRecord` and `get_pending_proposals()` are ready for article routing.

---

## Phase 3: User Story 1 — Web Clipper Articles → Knowledge Card (Priority: P1) 🎯 MVP

**Goal**: Files dropped in `data/raw/articles/` produce a four-section knowledge card wiki proposal automatically.

**Independent Test**: Save an Obsidian Web Clipper `.md` file to `data/raw/articles/`, run `uv run python src/batch_ingest.py`, then run `uv run python src/review_cli.py --type article`. Verify the proposal contains four distinct non-empty sections (Summary, Key Arguments/Findings, Core Concepts, Questions Raised/Open Questions).

- [x] T00x [P] [US1] Implement `src/article_parser.py` — a module with a single `parse(path: Path) -> Optional[NoteRecord]` function that: reads the file, strips YAML front matter (parse with `yaml.safe_load` on the block between `---` delimiters if present), extracts `title` (from YAML `title:`, first H1 `# `, or filename stem in that priority), extracts `source_url` (from YAML `url:` field, `None` if absent), stores `source_url` in `NoteRecord.tags` as `"url:{value}"` entry (temporary carrier until wiki_store reads it), sets `source="articles"`, `note_type="article"`, `id=SHA-256(body)`, and returns `None` with a printed skip message if `body.strip()` is empty
- [x] T00x [P] [US1] Add `KNOWLEDGE_CARD_PROMPT` constant and `generate_knowledge_card(body: str, domain_index: str) -> str` function to `src/ollama_agent.py` — the prompt instructs the model to produce exactly four H2 sections (`## Summary`, `## Key Findings` or `## Key Arguments`, `## Core Concepts`, `## Open Questions` or `## Questions Raised`), detect empirical vs opinion content by presence of words like "results/study/experiment/data/findings", use placeholder `_(insufficient content — revisit source)_` for unpopulatable sections, and pass `think=False` to `ollama.chat()` (existing convention)
- [x] T00x [US1] Add `render_knowledge_card(llm_output: str, related_slugs: list[str]) -> str` function to `src/wiki_store.py` — returns `llm_output` unchanged if `related_slugs` is empty; if non-empty, appends a `## Related Papers` section with each slug as `- [[{slug}]]` (depends on T008)
- [x] T01x [US1] Add `"articles"` branch to `_source_glob()` in `src/batch_ingest.py` — glob `data/raw/articles/*.md` (non-hidden files with `st_size > 0`), import and call `article_parser.parse()` for each file, skip `None` returns; set `source="articles"` routing (depends on T007)
- [x] T01x [US1] Route article notes through the knowledge card pipeline in `src/watcher.py` — in `_process_record()`, after classification, if `note.note_type == "article"` call `generate_knowledge_card()` instead of the standard `PROPOSAL_PROMPT`; extract `source_url` from `note.tags` and include `note_type` and `source_url` when calling `write_wiki_page()` front matter dict (depends on T007, T008, T009)
- [x] T01x [US1] Write unit tests for `src/article_parser.py` in `tests/unit/test_article_parser.py` — test: (a) file with full front matter extracts title/url/body correctly; (b) file without front matter uses H1 as title; (c) empty file returns None; (d) note_type is always "article"; (e) source is always "articles" (depends on T007)

**Checkpoint**: Web-clipped articles ingest and produce four-section knowledge card proposals in the review queue under `--type article`.

---

## Phase 4: User Story 2 — PDF Papers → Knowledge Card (Priority: P2)

**Goal**: PDF files dropped in `data/raw/papers/` have text extracted and produce the same four-section knowledge card as US1.

**Independent Test**: Place a multi-column research PDF in `data/raw/papers/`, run `uv run python src/batch_ingest.py`. Verify a NoteRecord is created with coherent extracted text and a four-section knowledge card proposal appears in `review_cli.py --type article`.

- [x] T01x [P] [US2] Implement `src/pdf_parser.py` — a module with `parse(path: Path) -> Optional[NoteRecord]` that: opens the PDF with `fitz.open(path)`, joins `page.get_text()` for all pages, if the joined result is empty/whitespace returns `None` after logging the error message `"no extractable text — OCR required"` to the `errors` table; extracts `title` from `doc.metadata.get("title")` if non-empty else filename stem; truncates body to 12,000 characters; sets `source="papers"`, `note_type="article"`, `id=SHA-256(body)`
- [x] T01x [US2] Add `"papers"` branch to `_source_glob()` in `src/batch_ingest.py` — glob `data/raw/papers/*.pdf` (non-hidden, `st_size > 0`), import and call `pdf_parser.parse()` for each file, skip `None` returns (depends on T013)
- [x] T01x [US2] Write unit tests for `src/pdf_parser.py` in `tests/unit/test_pdf_parser.py` — test: (a) a real or mock PDF with embedded text produces a NoteRecord with non-empty body; (b) an image-only PDF (mock `page.get_text()` returning empty string) returns None; (c) body is truncated at 12,000 chars; (d) note_type is always "article"; (e) source is always "papers" (depends on T013)

**Checkpoint**: PDF papers in `data/raw/papers/` ingest and produce knowledge card proposals; image-only PDFs are skipped with logged error.

---

## Phase 5: User Story 3 — `--type` Filter in Review CLI (Priority: P3)

**Goal**: `python src/review_cli.py --type article` shows only academic proposals; running without `--type` shows all proposals as before.

**Independent Test**: Ingest 3 article notes and 3 non-article notes. Run `review_cli.py --type article` — verify exactly 3 proposals appear. Run without `--type` — verify all 6 appear.

- [x] T01x [US3] Add `note_type: Optional[str] = None` parameter to `run_review()` in `src/review_cli.py` and thread it through to `get_pending_proposals(note_type=note_type)` (depends on T006)
- [x] T01x [US3] Parse `--type <value>` argument in the `__main__` block of `src/review_cli.py` and pass it to `run_review()` (depends on T016)

**Checkpoint**: `--type article` filters the queue precisely; existing behavior with no flag is unchanged.

---

## Phase 6: User Story 4 — Cross-Paper Wikilinks (Priority: P4)

**Goal**: New paper proposals include `[[wikilinks]]` to existing semantically-related article wiki pages (similarity > 0.75).

**Independent Test**: With 5+ article wiki pages committed, ingest a paper whose Core Concepts overlap with at least 2 existing pages. Verify the proposal includes a `## Related Papers` section with those slugs.

- [x] T01x [US4] Implement `find_related_article_pages(body: str, exclude_slug: str, top_k: int = 3) -> list[str]` in `src/wiki_store.py` — query the existing ChromaDB collection with the note body embedding, filter results to docs where front matter `note_type == "article"` (via metadata filter), exclude `exclude_slug`, return slugs whose similarity score ≥ 0.75 (up to `top_k`)
- [x] T01x [US4] Wire `find_related_article_pages()` into the article proposal pipeline in `src/watcher.py` — after generating the knowledge card body, call `find_related_article_pages()` with the note body and proposed slug, pass the result to `render_knowledge_card()` so the Related Papers section is included in the proposal (depends on T018)

**Checkpoint**: New paper proposals include `## Related Papers` when semantically related article pages exist; no spurious links when no overlap.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, format validation, and manual quickstart verification.

- [x] T02x [P] Verify that `write_wiki_page()` in `src/wiki_store.py` correctly writes `note_type` and `source_url` to the YAML front matter block for article pages — add these keys to the front matter dict construction if not already handled in T011
- [x] T02x Run the quickstart.md validation scenarios manually: clip a real web article, place a real PDF, run batch ingest, run `review_cli.py --type article`, verify proposals, approve one, confirm wiki page is committed with correct four-section structure and front matter fields

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — all six tasks can begin once T003–T006 are done
- **US2 (Phase 4)**: Depends on Phase 2 — can start in parallel with US1 (different files)
- **US3 (Phase 5)**: Depends on T006 (Phase 2) — lightweight, can overlap with US2
- **US4 (Phase 6)**: Depends on US1 being complete (needs ChromaDB-indexed article pages)
- **Polish (Phase 7)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — no inter-story dependencies
- **US2 (P2)**: Depends on Foundational only — shares watcher routing with US1 but different files
- **US3 (P3)**: Depends on T006 only — purely additive CLI change
- **US4 (P4)**: Depends on US1 being deployed (needs committed article wiki pages to search)

### Within Each User Story

- T007 and T008 can run in parallel (different files: `article_parser.py` vs `ollama_agent.py`)
- T009 depends on T008 (uses `generate_knowledge_card()` output)
- T010 depends on T007 (calls `article_parser.parse()`)
- T011 depends on T007, T008, T009 (uses all three)
- T012 depends on T007 (tests `article_parser.py`)
- T013 (US2) can run in parallel with all of US1 — independent file

---

## Parallel Opportunities

```text
# Phase 2 (Foundational — sequential):
T003 → T004 → T005 (schema → model → db methods)
T003 → T006 (independent of T004/T005)

# Phase 3 (US1 — partial parallel):
T007 [P]  T008 [P]   ← launch together (different files)
     ↓         ↓
T010      T009       ← each depends on one above
     ↓         ↓
         T011        ← depends on T007, T008, T009
T012               ← depends on T007 only, can run alongside T009/T010/T011

# Phase 4 (US2 — can start alongside Phase 3):
T013 [P]           ← can start the moment Phase 2 is done
     ↓
T014, T015         ← both depend on T013
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T006)
3. Complete Phase 3: US1 (T007–T012)
4. **STOP and VALIDATE**: Drop a real web-clipped article into `data/raw/articles/`, run ingest, review the four-section proposal
5. Ship US1 — this alone covers the most common workflow

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → web clip articles produce knowledge cards (MVP ✓)
3. US2 → PDF papers added to pipeline
4. US3 → `--type article` filter enables focused review sessions
5. US4 → cross-paper connections surface as wikilinks
6. Polish → quickstart validation confirms end-to-end flow

---

## Notes

- `think=False` MUST be passed to every `ollama.chat()` call (existing project convention — thinking tokens exhaust budget)
- `pymupdf` imports as `fitz` — `import fitz` in `pdf_parser.py`
- `note_type` is `None` for all existing notes — the `NULL` default is backwards-compatible
- The DB schema migration (T003) uses `try/except` around `ALTER TABLE` to stay idempotent across restarts
- All parsers must set `st_size > 0` guard (existing convention from batch_ingest fix)
- Body limit is 12,000 characters — same as all other sources (feature 003 convention)
