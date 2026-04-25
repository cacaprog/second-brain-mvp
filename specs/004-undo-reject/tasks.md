# Tasks: Undo Accidental Reject in Review

**Input**: Design documents from `/specs/004-undo-reject/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Two independent user stories. US1 (in-session undo) depends on T001 (DB helper). US2 (cross-session recovery) also uses T001 and can be implemented after US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: Which user story this task delivers (US1, US2)

---

## Phase 1: Setup

*No new project structure or dependencies needed — this feature modifies existing files only.*

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: The DB helper is required by both US1 and US2 — complete it first.

**⚠️ CRITICAL**: Complete T001 before starting any user story work.

- [x] T001 Add `undo_rejection(proposal_id: str, note_id: str) -> None` to the `DB` class in `src/db.py` — executes two SQL writes in a single connection: `UPDATE proposals SET decision=NULL, rejection_reason=NULL, decided_at=NULL WHERE id=?` and `UPDATE notes SET status='classified', modified_at=<now> WHERE id=?`; wrap in try/except and re-raise so callers can surface errors visibly (per Constitution Principle VII)

**Checkpoint**: DB helper ready — US1 and US2 implementation can begin.

---

## Phase 3: User Story 1 — In-Session Undo (Priority: P1) 🎯 MVP

**Goal**: Press `u` at any point in an active review session to undo the last rejection. The proposal returns immediately as the next item to review.

**Independent Test**: Open a review session with 2+ pending proposals. Press `r` on the first, enter a reason, press `u`. Verify the rejected proposal reappears as the next item and its DB status shows `decision=NULL` and `notes.status='classified'`.

- [x] T002 [US1] Modify `_handle_proposal(proposal, note, skip_queue)` in `src/review_cli.py` to accept two new mutable-list parameters: `undo_stack: list` (tracks rejected pairs for undo) and `restored: list` (output channel for the undone pair); when `r` is pressed and rejection is committed, `undo_stack.append((proposal, note))`; add `u` keypress branch: if `undo_stack` is empty print `"[dim]Nothing to undo[/dim]"` and continue; otherwise pop `(prev_proposal, prev_note)` from `undo_stack`, call `db.undo_rejection(prev_proposal.id, prev_note.id)`, print `"[yellow]↩ Rejection undone — proposal returned to queue[/yellow]"`, append `prev_proposal` to `restored`, and return `"undo"`

- [x] T003 [US1] Update `run_review()` in `src/review_cli.py` to initialize `undo_stack: list = []` and `restored: list = []`; pass both to `_handle_proposal()`; after each `_handle_proposal()` call, if `action == "undo"` and `restored` is non-empty: pop from `restored`, call `queue_items.insert(idx, restored_proposal)` to put it at the current position (the loop's `idx += 1` will then advance past it to show it next — so insert at `idx` and do NOT increment `idx` for this iteration); clear `restored` after consuming

- [x] T004 [P] [US1] Update the `?` help panel string in `_handle_proposal()` in `src/review_cli.py` — add `f"{_key('u')} Undo last rejection (this session only)"` after the `r` line in the `lines` list

**Checkpoint**: After T001–T004, in-session undo is fully functional. US1 acceptance criteria are met.

---

## Phase 4: User Story 2 — Cross-Session Recovery (Priority: P2)

**Goal**: Run `python src/review_cli.py --recover-rejected` to list notes rejected in the last 30 days and selectively restore them to the review queue.

**Independent Test**: Reject 3 notes and quit the session. Run `python src/review_cli.py --recover-rejected`. Verify all 3 appear in the numbered list with title, domain, and rejection date. Select one; verify `notes.status='classified'` and `proposals.decision=NULL` in the DB.

- [x] T005 [US2] Add `get_rejected_notes(days: int = 30) -> List[tuple[NoteRecord, Proposal]]` to the `DB` class in `src/db.py` — query: `SELECT n.*, p.id AS proposal_id, p.proposed_page, p.decided_at FROM notes n JOIN proposals p ON p.note_id = n.id WHERE n.status='rejected' AND n.modified_at >= datetime('now', '-' || ? || ' days') ORDER BY n.modified_at DESC` with `days` as parameter; return list of `(NoteRecord, Proposal)` tuples

- [x] T006 [US2] Add `run_recover_rejected()` function to `src/review_cli.py` — loads `db.get_rejected_notes(30)`; if empty prints `"[dim]No rejected notes in the last 30 days.[/dim]"` and returns; otherwise prints a numbered list: `[N] {note.title} [{note.domain}]  rejected: {decided_at[:10]}`; for each entry presents keybindings `[r] recover  [n] next  [q] quit`; on `r` calls `db.undo_rejection(proposal.id, note.id)` and prints `"[green]✓ Recovered — will appear in next review session[/green]"`; on `q` breaks; on any other key continues to next entry; ends with `"[bold]Recovery complete.[/bold]"`

- [x] T007 [US2] Update the `if __name__ == "__main__"` block in `src/review_cli.py` to add `elif "--recover-rejected" in sys.argv: run_recover_rejected()`; add this branch before the `else` that calls `run_review()`

**Checkpoint**: After T005–T007, cross-session recovery is functional. US2 acceptance criteria are met.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T008 [P] Add unit tests for `db.undo_rejection()` and `db.get_rejected_notes()` in `tests/unit/test_review_undo.py` — create a temp SQLite DB, insert a note + proposal with status `rejected` and `decision='rejected'`, call each method, assert the DB state is correctly updated
- [ ] T009 Manually run the quickstart scenarios from `specs/004-undo-reject/quickstart.md`: (1) in-session undo, (2) `--recover-rejected` with at least one rejected note, (3) `--recover-rejected` when no rejections exist; verify all 3 behave as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: T001 fully blocks US1 and US2 — start immediately
- **US1 (Phase 3)**: T002, T003, T004 all depend on T001; T002 and T003 are sequential (T003 depends on T002's new signature); T004 is parallel (touches the same file but only the help string)
- **US2 (Phase 4)**: T005 is parallel with US1 (different DB method); T006 depends on T005; T007 depends on T006
- **Polish (Phase 5)**: T008 can start after T001; T009 requires all prior tasks complete

### User Story Dependencies

- **US1**: Depends on T001 only
- **US2**: Depends on T001; independent of US1 (uses the same DB helper but different CLI function)

### Within Each Phase

- T002 → T003 (T003 updates the caller of T002's modified function signature)
- T004 can be written concurrently with T002/T003 (same file, separate function section)
- T005 → T006 → T007 (sequential within US2)

### Parallel Opportunities

```bash
# Start immediately:
Task T001: "Add undo_rejection() to src/db.py"

# After T001:
Task T002: "Modify _handle_proposal() in src/review_cli.py"    ← US1 critical path
Task T005: "Add get_rejected_notes() to src/db.py"             ← US2 start, parallel

# After T002:
Task T003: "Update run_review() in src/review_cli.py"
Task T004: "Update ? help panel in src/review_cli.py"          ← parallel with T003

# After T005:
Task T006: "Add run_recover_rejected() to src/review_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001 (DB helper)
2. Complete T002 + T003 + T004 (US1 review CLI changes)
3. **STOP and VALIDATE**: manually test in-session undo with a real proposal in the review queue
4. Confirm undo reverses DB state and proposal reappears before adding US2

### Incremental Delivery

1. T001 → Foundation complete
2. T002–T004 → US1 done (in-session undo works)
3. T005–T007 → US2 done (cross-session recovery works)
4. T008–T009 → Polish and validated

---

## Notes

- T001 is the only critical-path item before any user story work — unblock it first
- T002 and T003 both touch `review_cli.py` and must be done sequentially; plan a single focused session
- T004 is deliberately separated from T002/T003 because it is trivially parallel (help text only) and should not block US1 completion
- T009 is a manual validation step — allocate ~10 minutes after all code is done
- The `undo_stack` and `restored` list approach (T002–T003) avoids changing `_handle_proposal`'s return type from `Optional[str]`, keeping backward compatibility with all existing `if action == "..."` checks in `run_review()`
