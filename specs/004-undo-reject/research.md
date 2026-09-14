# Research: Undo Accidental Reject in Review

## Decision 1: Undo Stack Data Structure

**Decision**: An in-memory list of `(proposal, note)` tuples maintained inside `run_review()`, passed by reference to `_handle_proposal()`. Each rejected pair is appended; `u` pops from the end (LIFO).

**Rationale**: The session is single-threaded and single-user. A plain list is sufficient — no concurrency concerns, no persistence needed. LIFO order correctly implements "most recent first" undo semantics. The list is bounded by the number of rejections in a single session (typically ≤ 50).

**Alternatives considered**:
- Separate undo module / class — rejected as overengineering for a single-list, single-caller use case
- Persisted undo log — rejected; `--recover-rejected` handles the cross-session case; mixing the two would add complexity without benefit

---

## Decision 2: DB State for Undo

**Decision**: Undo performs two writes:
1. `UPDATE proposals SET decision=NULL, rejection_reason=NULL, decided_at=NULL WHERE id=?`
2. `UPDATE notes SET status='classified' WHERE id=?`

**Rationale**: `get_pending_proposals()` filters on `decision IS NULL`. Clearing the decision makes the proposal reappear in future sessions' queues. Setting note status back to `classified` is the correct pre-review state (that is what `watcher.py` sets when creating a proposal). No new DB method is needed — a raw `conn.execute` or a new `db.undo_rejection(proposal_id, note_id)` helper are both viable; a named helper is preferred for clarity.

**Alternatives considered**:
- Add a `PENDING_REVIEW` status (already defined in `models.py` but unused) — rejected; `classified` is already the correct pre-review state and adding a new status would require changes across the pipeline for no benefit
- Keep `decision='rejected'` and add an `undone=1` flag — rejected; this complicates `get_pending_proposals` and creates ambiguous state

---

## Decision 3: Re-inserting the Undone Proposal Into the Active Queue

**Decision**: After undo, insert the `(proposal, note)` pair at the current `idx` position in `queue_items` so it is the next proposal shown, then decrement `idx` by 1 (or equivalently, call `queue_items.insert(idx, proposal)` before the loop increments).

**Rationale**: The user expects to see the undone proposal immediately after pressing `u` — not at the end of the queue. Inserting at the current position achieves this without re-sorting the list or changing the loop structure.

**Alternatives considered**:
- Append to end of queue — rejected; user pressed `u` because they want to fix it now, not encounter it again 30 proposals later
- Re-run `db.get_pending_proposals()` — rejected; overkill and would reset position in the queue for all other proposals

---

## Decision 4: `--recover-rejected` Query

**Decision**: Query `notes WHERE status='rejected' AND modified_at >= datetime('now', '-30 days')`, joined with `proposals` to get `proposed_page` and `decided_at` for display. The user selects notes to restore via numbered list + keypress (not a full review render).

**Rationale**: The `notes.modified_at` timestamp is updated by `set_note_status()`, so it accurately reflects when the note was rejected. A 30-day window is long enough for realistic accident recovery and short enough to not surface intentional old rejections. The interaction is a lightweight numbered list (not the full diff render) because the user is recovering, not re-reviewing.

**Alternatives considered**:
- Filter by `proposals.decided_at` — same result since both timestamps are set at rejection time; `notes.modified_at` is simpler (no join required for the filter)
- Interactive full re-review during `--recover-rejected` — rejected; the recovery flow is distinct from the review flow; user can re-review after recovery

---

## Decision 5: Scope of Undo (Rejections Only)

**Decision**: `u` undoes only rejections. Approvals and fast-tracks are out of scope.

**Rationale**: Approvals and fast-tracks write to the wiki (git commit). Reverting them requires `git revert` + ChromaDB re-indexing — a separate, heavier operation. The existing `--batch-log` review mode already supports reverting fast-tracked proposals. Scope is deliberately bounded to the simplest, highest-value case.

**Alternatives considered**:
- Undo approve — rejected; requires wiki revert machinery not in scope here
- Generic undo for all actions — rejected; over-engineering; the most common accident is accidental rejection, per the spec
