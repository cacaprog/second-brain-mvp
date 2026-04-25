# Tasks: Wiki Slug Duplicate Merger

**Input**: Design documents from `/specs/007-merge-slug-duplicates/`
**Branch**: `007-merge-slug-duplicates`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

No new packages or project structure changes required. All new code follows the existing single-file CLI pattern (`wiki_cleaner.py`). Proceed directly to Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Helper functions that every user story depends on, plus the wiki_merger.py skeleton with shared data structures and utilities.

**⚠️ CRITICAL**: All tasks in this phase must be complete before any user story phase begins.

- [x] T001 Add `remove_slug_from_index(domain: str, slug: str) -> None` to `src/wiki_store.py` — remove a table row matching `| slug |` from the domain's `index.md`
- [x] T002 Add `delete_wiki_page(domain: str, slug: str) -> None` to `src/wiki_store.py` — delete `wiki/domains/{domain}/{slug}.md` from disk (no git commit; git is the user's undo)
- [x] T003 [P] Add `delete_embedding(slug: str, domain: str) -> None` to `src/vector_store.py` — call `collection.delete(ids=[slug])` on the domain's ChromaDB collection; no-op if slug not found
- [x] T004 [P] Add `get_notes_by_wiki_page(wiki_page: str) -> list[str]` and `clear_wiki_page(wiki_page: str) -> None` to `src/db.py` — SELECT note IDs, then `UPDATE notes SET wiki_page=NULL WHERE wiki_page=?`
- [x] T005 Create `src/wiki_merger.py` with: `PageEntry` dataclass, `DuplicateGroup` dataclass, `MergeOutcome` dataclass, `normalize_slug()`, `_load_page()`, `_merge_front_matter()`, `_build_page_content()`, and `_consolidate_bodies()` (imports `_consolidate` from `wiki_cleaner`)

**Checkpoint**: ✅ Helper functions in place, wiki_merger.py created — user story phases can now proceed.

---

## Phase 3: User Story 1 — Detect All Duplicate Slugs (Priority: P1) 🎯 MVP

**Goal**: Safe, read-only scan that reports all same-domain near-duplicate pairs AND all cross-domain slug groups in a single command.

**Independent Test**: `python src/wiki_merger.py detect` reports known pairs without modifying any files. ✅ Verified.

- [x] T006 [US1] Implement `detect_same_domain_pairs() -> list[DuplicateGroup]` in `src/wiki_merger.py`
- [x] T007 [P] [US1] Implement `detect_cross_domain_groups() -> list[DuplicateGroup]` in `src/wiki_merger.py`
- [x] T008 [US1] Implement `_select_canonical_same_domain(pages)` in `src/wiki_merger.py`
- [x] T009 [US1] Add `detect` subcommand to `src/wiki_merger.py` CLI

**Checkpoint**: ✅ `python src/wiki_merger.py detect` works and reports all known duplicates.

---

## Phase 4: User Story 2 — Merge a Single Near-Duplicate Pair (Priority: P1)

**Goal**: Accept two or more page file paths, merge all non-canonical pages into the canonical, and clean up all stores.

- [x] T010 [US2] Implement `_merge_group(group, dry_run, cfg) -> MergeOutcome` in `src/wiki_merger.py`
- [x] T011 [US2] Add `merge` subcommand to `src/wiki_merger.py` CLI with `--keep` and `--dry-run`

**Checkpoint**: ✅ `python src/wiki_merger.py merge FILE1 FILE2 --dry-run` works correctly.

---

## Phase 5: User Story 3 — Cross-Domain Merge (Priority: P2)

**Goal**: Extend merge logic to handle pages in different domains.

- [x] T012 [US3] Implement `_select_canonical_cross_domain(pages)` in `src/wiki_merger.py`
- [x] T013 [US3] `_merge_group()` uses `redundant.domain` per redundant page for cross-domain deletes

**Checkpoint**: ✅ Cross-domain merge handled correctly in `_merge_group()`.

---

## Phase 6: User Story 4 — Batch Merge All (Priority: P2)

**Goal**: One command that detects and merges all groups in correct order.

- [x] T014 [US4] Implement `run_batch(dry_run, cfg)` in `src/wiki_merger.py`
- [x] T015 [US4] Add `batch` subcommand to `src/wiki_merger.py` CLI with `--dry-run`

**Checkpoint**: ✅ `python src/wiki_merger.py batch --dry-run` shows all groups, no writes.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T016 [P] Edge cases handled: identical bodies skip LLM (`[SKIP-LLM]`); empty body aborts write; missing index entry is silent no-op; 3+ page groups work via list iteration
- [x] T017 [P] Output matches `contracts/cli.md`: detect has both sections + summary; merge shows sources/links delta; batch shows per-type summary
- [x] T018 `uv tool run ruff check src/wiki_merger.py src/wiki_store.py src/vector_store.py src/db.py` — all checks passed ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 Detect (Phase 3)**: Depends on Phase 2 complete
- **US2 Single Merge (Phase 4)**: Depends on Phase 2 + Phase 3
- **US3 Cross-Domain (Phase 5)**: Depends on Phase 4
- **US4 Batch (Phase 6)**: Depends on Phases 3 + 4 + 5
- **Polish (Phase 7)**: Depends on all prior phases

### Notes

- T003 and T004 are [P] — different files
- T006 and T007 are [P] — independent detection algorithms
- T016 and T017 are [P] — no shared state
- Always test with `--dry-run` before a real batch run
- Use `git diff wiki/` after any merge to verify only expected changes occurred
