# Data Model: Undo Accidental Reject

No new tables or columns are introduced. The feature operates entirely on existing schema.

## Existing Fields Used

### `proposals` table

| Column | Type | Undo behavior |
|--------|------|---------------|
| `decision` | TEXT (nullable) | Set to `NULL` on undo — makes the proposal reappear in `get_pending_proposals()` |
| `rejection_reason` | TEXT (nullable) | Set to `NULL` on undo |
| `decided_at` | TEXT (nullable) | Set to `NULL` on undo |

### `notes` table

| Column | Type | Undo behavior |
|--------|------|---------------|
| `status` | TEXT | Restored to `'classified'` on undo (the pre-review state set by `watcher.py`) |
| `modified_at` | TEXT | Updated by `set_note_status()` — used by `--recover-rejected` to filter notes rejected in the last 30 days |

## In-Memory State (not persisted)

### Undo Stack

A plain Python list of `(Proposal, NoteRecord)` tuples, scoped to the `run_review()` call. Appended to on each rejection; popped (LIFO) on each undo. Cleared when the session ends.

```
undo_stack: list[tuple[Proposal, NoteRecord]]
```

## State Transition

```
CLASSIFIED → (user presses r) → REJECTED
                ↑
        (user presses u)
```

After undo, the note returns to `CLASSIFIED` status and its proposal's `decision` is `NULL`, making it eligible for review in the current session (inserted at current queue position) and in future sessions (picked up by `get_pending_proposals()`).
