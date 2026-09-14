# Tasks: Rich Note Knowledge Cards — Paragraph-Based Knowledge Card Routing

**Input**: Design documents from `/specs/009-rich-note-knowledge-cards/`  
**Branch**: `009-rich-note-knowledge-cards`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

No new packages or project structure changes required. All changes are additions to
existing files. Proceed directly to Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The settings key and paragraph counter are needed by every user story.
Both touch different files with no interdependency — parallelisable.

**⚠️ CRITICAL**: Both tasks must be complete before any user story phase begins.

- [x] T001 [P] Add `rich_note_paragraph_threshold: 4` under the `ingestion:` block in `config/settings.yaml` — place it after `fast_track_confidence`
- [x] T002 [P] Add `_count_paragraphs(body: str) -> int` as a module-level helper in `src/watcher.py` — split on `r"\n{2,}"`, filter empty strings, return count; place before `_process_record`

**Checkpoint**: Both helpers available and manually verifiable in isolation.

---

## Phase 3: User Story 1 — Long Notes Produce Structured Wiki Pages (Priority: P1) 🎯 MVP

**Goal**: Notes with ≥ threshold paragraphs are routed to the knowledge-card path and
produce a structured four-section wiki page.

**Independent Test**: Run a Kindle or Notion note with 4+ paragraphs through
`watcher.py --once`. Confirm the resulting wiki page has `note_type: rich_note` in
front matter and contains multiple `##` sections. Run a note with 3 paragraphs and
confirm it produces a standard proposal with a single prose summary.

- [x] T003 [US1] In `src/watcher.py:_process_record()`, add paragraph-count check before `db.upsert_note(note)` (line ~129): load threshold from settings, call `_count_paragraphs(note.body)`, set `note.note_type = "rich_note"` when count ≥ threshold and `note_type` is not `"article"` or `"paper"`
- [x] T004 [US1] In `src/watcher.py:_process_record()`, update the propose-block routing condition from `if note.note_type == "article":` to `if note.note_type in ("article", "rich_note"):` so rich notes enter the knowledge-card branch
- [x] T005 [US1] In `src/wiki_store.py:render_knowledge_card_page()`, add `note_type: str = "article"` parameter and replace the hard-coded `"note_type": "article"` in the front matter dict with the parameter value
- [x] T006 [US1] Update both callers of `render_knowledge_card_page()` to pass `note_type=note.note_type`: in `src/watcher.py` (article/rich_note branch) and in `src/commit.py` (article branch)

**Checkpoint**: `python src/watcher.py --once <note-with-4-paragraphs>` produces a wiki
page with `note_type: rich_note` and four `##` sections. A note with 3 paragraphs still
goes through `generate_proposal()` and produces a standard flat summary.

---

## Phase 4: User Story 2 — Threshold Is Configurable (Priority: P2)

**Goal**: The paragraph threshold can be changed in `config/settings.yaml` without
touching source code.

**Independent Test**: Set `rich_note_paragraph_threshold: 5` in settings, run a note
with 4 paragraphs — confirm it takes the standard path. Restore to 4, re-run — confirm
it takes the knowledge-card path.

> **No new tasks.** User Story 2 is fully satisfied by T001 (config key) and T003
> (reading the key via `cfg["ingestion"].get("rich_note_paragraph_threshold", 4)`).
> The default value of 4 in `.get()` also ensures the system works even if the key is
> absent from older settings files.

**Checkpoint**: Edit threshold in `config/settings.yaml`, re-run pipeline, observe
routing change with no code modification required.

---

## Phase 5: User Story 3 — Review TUI Label (Priority: P3)

**Goal**: Proposals generated from rich notes display a `[RICH NOTE]` label in the
review TUI so reviewers can distinguish them from standard proposals.

**Independent Test**: Process a rich note (≥ threshold paragraphs) so it lands in the
review queue, then run `python src/review_cli.py`. Confirm the proposal header shows
`RICH NOTE` in green. Run a standard note proposal and confirm no such label appears.

- [x] T007 [US3] In `src/review_cli.py:_render_diff()`, add `rich_label` variable: `"  [bold green]RICH NOTE[/bold green]"` when `note.note_type == "rich_note"`, else `""` — append to the existing `console.print(...)` header line that shows `conf:` and `flag`

**Checkpoint**: `review_cli.py` header for a rich-note proposal shows `RICH NOTE` in
green alongside domain and confidence. Standard proposals unchanged.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T008 [P] `uv tool run ruff check src/watcher.py src/wiki_store.py src/review_cli.py src/commit.py` — all checks pass ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on T001 + T002 (needs settings key and `_count_paragraphs`)
- **US2 (Phase 4)**: Fully covered by T001 + T003 — no additional tasks
- **US3 (Phase 5)**: Depends on T003 (needs `note_type = "rich_note"` persisted in DB)
- **Polish (Phase 6)**: Depends on all prior phases

### Task Execution Order

```
T001 ──┐
       ├── T003 ── T004 ── T005 ── T006 ── T007 ── T008
T002 ──┘
```

### Parallel Opportunities

T001 and T002 are `[P]` — different files, no shared state, can be done simultaneously.
All remaining tasks are sequential (each builds on the previous routing change).

---

## Parallel Example: Foundational Phase

```
Task: "Add rich_note_paragraph_threshold: 4 to config/settings.yaml"
Task: "Add _count_paragraphs() helper to src/watcher.py"
```

---

## Implementation Strategy

### MVP (User Story 1 only — 6 tasks total)

1. T001 + T002 in parallel (Foundational)
2. T003 → T004 → T005 → T006 sequentially (US1)
3. T008 (ruff check)
4. **Validate**: `python src/watcher.py --once <4-paragraph-note>` → structured wiki page

### Full Delivery

1. Foundational (T001 + T002)
2. US1 (T003–T006) — routing + render param
3. US2 — free: validated via threshold edit test (no new code)
4. US3 (T007) — TUI label
5. Polish (T008)
