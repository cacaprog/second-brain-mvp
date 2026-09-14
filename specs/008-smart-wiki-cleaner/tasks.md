# Tasks: Smart Wiki Cleaner — Content-Aware Consolidation

**Input**: Design documents from `/specs/008-smart-wiki-cleaner/`  
**Branch**: `008-smart-wiki-cleaner`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)

---

## Phase 1: Setup

No new packages or project structure changes required. All changes are in `src/wiki_cleaner.py`. Proceed directly to Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Helper functions that every user story depends on. Both are additions to `src/wiki_cleaner.py` and can be written in parallel (no interdependency).

**⚠️ CRITICAL**: All tasks in this phase must be complete before any user story phase begins.

- [x] T001 [P] Add `_deduplicate_paragraphs(paragraphs: list[str]) -> list[str]` to `src/wiki_cleaner.py` — iterates paragraphs, keeps first occurrence of each (strip+lower key), returns list in original order
- [x] T002 [P] Add `_is_article_page(slug: str, db) -> bool` to `src/wiki_cleaner.py` — calls `db.get_notes_by_wiki_page(slug)` to get note IDs, then queries `db.get_note(note_id).note_type` for each; returns `True` if any note has `note_type == "article"`; returns `False` for orphaned pages (no rows)

**Checkpoint**: Both helpers implemented and manually verifiable in isolation.

---

## Phase 3: User Story 1 — Article Pages Are Never Touched (Priority: P1)

**Goal**: Article/paper wiki pages are skipped before any content analysis runs.

**Independent Test**: `python src/wiki_cleaner.py --dry-run` shows `skipped (article)` for every page linked to notes with `note_type="article"`. No file is modified.

- [x] T003 [US1] Update `_process_page()` signature in `src/wiki_cleaner.py` to accept `db` as a fourth parameter; after the `len(paragraphs) <= 2` guard, add article check using `_is_article_page(slug, db)` — return `"skipped_article"` if true
- [x] T004 [US1] Update `run()` in `src/wiki_cleaner.py` to instantiate `DB` once via `get_db()` and pass it to every `_process_page()` call; add `from db import get_db` import

**Checkpoint**: `python src/wiki_cleaner.py --dry-run --path <article-page>` prints `skipped (article)` without calling Ollama.

---

## Phase 4: User Story 2 — Non-Repetitive Pages Preserved as Composite Knowledge (Priority: P1)

**Goal**: Pages whose paragraphs are all unique are left unchanged.

**Independent Test**: `python src/wiki_cleaner.py --path <page-with-unique-paragraphs> --dry-run` prints `skipped (no repetition)` and shows no LLM output.

- [x] T005 [US2] After the article check in `_process_page()` in `src/wiki_cleaner.py`, call `_deduplicate_paragraphs(paragraphs)` to get `unique`; if `len(unique) == len(paragraphs)`, return `"skipped_no_rep"` (no duplicates found)

**Checkpoint**: A page with 4 distinct paragraphs returns `skipped_no_rep`; a page with 4 paragraphs including one duplicate proceeds past this guard.

---

## Phase 5: User Story 3 — Repetitive Pages Are Consolidated (Priority: P1)

**Goal**: Pages with proven duplicate content are either directly deduped (if ≤2 unique remain) or LLM-consolidated (if 3+ unique remain).

**Independent Test**: `python src/wiki_cleaner.py --path <page-with-repetition> --dry-run` shows the consolidated body; running without `--dry-run` writes the result.

- [x] T006 [US3] After the no-repetition guard in `_process_page()` in `src/wiki_cleaner.py`, handle the two sub-cases: if `len(unique) <= 2`, rebuild the page with the unique paragraphs directly (no LLM call) and return `"deduped"`; else call `_consolidate(unique, cfg)` and return `"consolidated"` — also handle dry-run preview for the `deduped` path

**Checkpoint**: A page with 6 identical paragraphs returns `deduped` (single paragraph written, no LLM); a page with 3 paragraphs where 1 is a duplicate returns `deduped` (2 paragraphs written, no LLM); a page with 4 paragraphs where 1 is a duplicate returns `consolidated` (3 unique → LLM call).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T007 [P] Update summary counters in `run()` in `src/wiki_cleaner.py` — replace the single `changed`/`skipped` buckets with: `consolidated`, `deduped`, `skipped_short` (was `skipped`), `skipped_article`, `skipped_no_rep`, `errored`; update the summary print line to show all six categories
- [x] T008 [P] Update `_process_page()` print statements in `src/wiki_cleaner.py` — print `[SKIP-ARTICLE]`, `[SKIP-NO-REP]`, `[DEDUPED]` prefix lines to match the action; keep `[CONSOLIDATE]` for LLM path; keep `[DONE]` for successful writes
- [x] T009 `uv tool run ruff check src/wiki_cleaner.py` — all checks pass ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 Article Guard (Phase 3)**: Depends on T002 (needs `_is_article_page`)
- **US2 No-Rep Guard (Phase 4)**: Depends on T001 (needs `_deduplicate_paragraphs`) and T003/T004
- **US3 Consolidation Path (Phase 5)**: Depends on T005 (guard chain must be in place)
- **Polish (Phase 6)**: Depends on all prior phases

### Notes

- T001 and T002 are [P] — no shared state
- T007 and T008 are [P] — different lines in `run()` vs `_process_page()`
- All logic changes are in a single file (`src/wiki_cleaner.py`)
- Always test with `--dry-run` before a real run
- The `deduped` return path must also handle `dry_run=True` (show old vs new, no write)
