# Tasks: Kindle Multi-Domain Ingest

**Input**: Design documents from `/specs/002-kindle-multi-domain/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story. US1 and US2 share the same core parser rewrite (both are consequences of per-highlight grouping). US3's thin-group merging is an additional quality layer on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: Which user story this task delivers (US1, US2, US3)

---

## Phase 1: Setup

*Project already initialized — no setup tasks needed.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Four independent supporting pieces that all user stories depend on. All can be done in parallel.

**⚠️ CRITICAL**: Complete this phase before touching `kindle_parser.py`.

- [x] T001 [P] Add `keyword_classify(body: str, domains: dict | None = None) -> str` to `src/classifier.py` — keyword scoring only (Stage 1), no embedding model load, returns domain name with highest score or first domain as fallback; accepts optional pre-loaded domains dict to avoid repeated YAML reads per highlight
- [x] T002 [P] Add `kindle.min_group_size: 3` section to `config/settings.yaml` under a new `kindle:` top-level key
- [x] T003 [P] Add `get_notes_by_path_prefix(prefix: str) -> List[NoteRecord]` and `delete_note(note_id: str) -> None` to the `DB` class in `src/db.py` — `get_notes_by_path_prefix` uses `SELECT * FROM notes WHERE source_path LIKE ? || '%'`; `delete_note` uses `DELETE FROM notes WHERE id = ?`
- [x] T004 Update `_already_processed()` in `src/batch_ingest.py` for Kindle `.txt` files: call `db.get_notes_by_path_prefix(str(file_path.resolve()) + "#")`; if none exist return False; if any note's `source_path` contains exactly two `#` characters return True (new format, already processed); if all have one `#` (old format) call `db.delete_note()` for each and return False to trigger re-ingestion (depends on T003)

**Checkpoint**: Foundation ready — `kindle_parser.py` rewrite can begin.

---

## Phase 3: User Story 1 — Full Highlight Coverage (Priority: P1) 🎯 MVP

**Goal**: Every highlight in every Kindle book is captured in at least one NoteRecord, regardless of position or book length. No highlight is silently dropped.

**Independent Test**: Ingest a Kindle file containing a book with 100+ highlights. Query `SELECT source_path, word_count FROM notes WHERE source LIKE 'kindle%'` and confirm that word counts for that book's records account for highlights from the second half of the file.

- [x] T005 [US1] Rewrite `parse_to_records()` in `src/kindle_parser.py` — implement the 4-step pipeline:
  - **Step 1 — Parse** (keep existing logic): group raw highlight texts per book title
  - **Step 2 — Classify per highlight**: call `classifier.keyword_classify(highlight_text, domains)` for each highlight; load `domains` once per file via `_load_domains()`; accumulate `dict[domain_name → list[str]]` per book
  - **Step 3 — Merge thin groups**: for each book, find groups with fewer than `settings.kindle.min_group_size` highlights; reassign each thin-group highlight to the domain with the next-highest keyword score for that specific highlight; if only one domain remains that is the correct single-domain outcome
  - **Step 4 — Create NoteRecords**: for each surviving domain group create one `NoteRecord` with `source_path = f"{file_path.resolve()}#{_slugify(book_title)}#{domain}"`, `id = SHA-256(f"{book_title}\n{domain}\n{body}")`, `title = f"{book_title} [{domain}]"` if book has 2+ groups else `book_title`, `domain` pre-set to the group's domain; all other fields unchanged from current implementation
- [x] T006 [P] [US1] Create `tests/unit/test_kindle_parser.py` with test `test_all_highlights_captured`: build a synthetic clippings string with one book containing 20 highlights; call `KindleParser.parse_to_records()`; assert that the total highlight count across all returned NoteRecords equals 20 (join all bodies on `---` and count separators)

**Checkpoint**: After T005+T006, every highlight is represented in a NoteRecord. US1 acceptance criteria are met.

---

## Phase 4: User Story 2 — Multi-Domain Assignment (Priority: P2)

**Goal**: A book with highlights spanning distinct domains produces separate NoteRecords for each domain, each going through the pipeline independently.

**Independent Test**: Ingest a synthetic clippings file with Book A (10 highlights using "philosophy" seeds + 10 highlights using "analytics" seeds). Assert that `parse_to_records()` returns 2 NoteRecords for Book A with different `domain` fields.

- [x] T007 [P] [US2] Add test `test_multi_domain_book` to `tests/unit/test_kindle_parser.py`: build a clippings string with Book A having 10 highlights full of `config/domains.yaml` seeds for domain X and 10 highlights full of seeds for domain Y; assert that `parse_to_records()` returns exactly 2 records for Book A, each with `domain` matching X and Y respectively, and that `source_path` ends with `#domain-x` and `#domain-y`
- [x] T008 [P] [US2] Add test `test_single_domain_book_no_split` to `tests/unit/test_kindle_parser.py`: book with all 15 highlights clearly in one domain must produce exactly 1 NoteRecord (no spurious splitting) and `title` must equal bare book title without domain suffix
- [x] T009 [US2] Verify end-to-end pipeline integration: run `uv run python src/watcher.py --once data/raw/kindle/my_clippings.txt` and confirm via `sqlite3 db/brain.sqlite "SELECT title, domain, word_count FROM notes WHERE source='kindle' ORDER BY title, domain"` that multi-domain books produce multiple rows and single-domain books produce one row

**Checkpoint**: After T007–T009, multi-domain books produce independent proposals per domain. US2 acceptance criteria are met.

---

## Phase 5: User Story 3 — Coherent Per-Domain Groupings (Priority: P3)

**Goal**: Thin groups (below `min_group_size`) are merged into the best-matching domain group rather than producing low-quality standalone wiki proposals. Resulting groups are thematically coherent.

**Independent Test**: Build a synthetic book with 15 highlights in domain A and 2 highlights in domain B (below threshold). Assert that the 2 thin highlights are merged into domain A's group, producing one NoteRecord with 17 highlights' content.

- [x] T010 [P] [US3] Add test `test_thin_group_merging` to `tests/unit/test_kindle_parser.py`: book with 15 highlights in domain A seeds + 2 highlights in domain B seeds (min_group_size=3); assert `parse_to_records()` returns exactly 1 NoteRecord containing all 17 highlights (not 2 records)
- [x] T011 [P] [US3] Add test `test_single_highlight_book` to `tests/unit/test_kindle_parser.py`: book with only 1 highlight total; assert it produces 1 NoteRecord with that highlight (no crash, no merging loop)
- [ ] T012 [US3] Manual coherence review: after T009 re-ingestion produces proposals in the review queue, run `uv run python src/review_cli.py` and inspect 3–5 proposals from multi-domain books; verify that each proposal summary reads as a concept-focused statement (no mixed-topic summaries); record any incoherent groupings for threshold tuning

**Checkpoint**: After T010–T012, thin-group merging works and group coherence is validated. US3 acceptance criteria are met.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end integration test and operational acceptance gate.

- [x] T013 [P] Create `tests/integration/test_kindle_pipeline.py`: write a synthetic `My Clippings.txt` to a temp dir containing Book A (10 philosophy + 10 analytics highlights), Book B (5 analytics highlights — single domain), Book C (2 philosophy highlights — below threshold, should merge into philosophy); run `_parse_note(tmp_path / "my_clippings.txt")`; assert: Book A → 2 records, Book B → 1 record, Book C's 2 highlights merged into Book C's sole group (1 record), total highlight count across all records = 27, all `source_path` values match `file#slug#domain` pattern (contain exactly 2 `#` characters)
- [ ] T014 Re-ingest all existing Kindle files to complete migration from old format: `uv run python src/batch_ingest.py --dir data/raw/kindle`; verify no old-format records remain via `sqlite3 db/brain.sqlite "SELECT source_path FROM notes WHERE source='kindle' AND source_path NOT LIKE '%#%#%'"` (should return 0 rows); monitor review queue for new multi-domain proposals

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: T001–T003 fully parallel; T004 depends on T003 — start last
- **US1 (Phase 3)**: T005 depends on T001+T002 (needs `keyword_classify` and `min_group_size`); T006 can be written concurrently with T005
- **US2 (Phase 4)**: T007+T008 can be written concurrently with T005; T009 depends on T005 completing
- **US3 (Phase 5)**: T010+T011 can be written after T005; T012 depends on T009
- **Polish (Phase 6)**: T013 depends on T005; T014 depends on T005+T004

### User Story Dependencies

- **US1**: Depends on Phase 2 (T001, T002)
- **US2**: Depends on US1 completion (T005) — multi-domain is a property of the same parser rewrite
- **US3**: Depends on US1 completion (T005) — thin-group merging is part of Step 3

### Within Each Phase

- Foundational tasks (T001–T003): start in parallel immediately
- Parser rewrite (T005): is the critical path item — start as soon as T001+T002 are done
- Unit tests (T006–T008, T010–T011): can be written concurrently with T005 (TDD-friendly)

### Parallel Opportunities

```bash
# All of these can start immediately:
Task T001: "Add keyword_classify() to src/classifier.py"
Task T002: "Add kindle.min_group_size to config/settings.yaml"
Task T003: "Add migration methods to src/db.py"

# After T003 completes:
Task T004: "Update _already_processed() in src/batch_ingest.py"

# After T001 + T002:
Task T005: "Rewrite parse_to_records() in src/kindle_parser.py"  ← critical path

# Concurrently with T005:
Task T006: "Write test_all_highlights_captured in tests/unit/test_kindle_parser.py"
Task T007: "Write test_multi_domain_book in tests/unit/test_kindle_parser.py"
Task T008: "Write test_single_domain_book_no_split in tests/unit/test_kindle_parser.py"
Task T010: "Write test_thin_group_merging in tests/unit/test_kindle_parser.py"
Task T011: "Write test_single_highlight_book in tests/unit/test_kindle_parser.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001 + T002 + T003 + T004 (Foundational)
2. Complete T005 + T006 (US1 parser rewrite + basic test)
3. **STOP and VALIDATE**: `uv run pytest tests/unit/test_kindle_parser.py -v`
4. Confirm all highlights are captured before adding multi-domain splitting

### Incremental Delivery

1. T001–T004 → Foundation complete
2. T005+T006 → US1 (all highlights captured)
3. T007–T009 → US2 (multi-domain proposals in queue)
4. T010–T012 → US3 (thin groups merged, coherence confirmed)
5. T013–T014 → Full system validated, existing files migrated

---

## Notes

- `kindle_parser.py` (T005) is the only critical-path item — unblock it by completing T001+T002 first
- All unit tests (T006–T011) touch the same file (`test_kindle_parser.py`) — write them sequentially or merge into a single session
- T012 is a manual review step, not automated — allocate time to read actual proposals
- T014 (re-ingest) is the real-world acceptance gate; SC-001 and SC-002 from the spec are verified here
- The `think=False` parameter is already set in `ollama_agent.py` — no change needed for Ollama calls
