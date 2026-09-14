# Quickstart: Undo Accidental Reject

## Scenario 1 — In-session undo (most common)

```bash
uv run python src/review_cli.py
```

1. Review appears. You press `r` by accident.
2. Enter a rejection reason (or press Enter for empty reason) — the proposal is rejected.
3. Immediately press `u`.
4. Console prints: `↩ Rejection undone — proposal returned to queue`
5. The accidentally-rejected proposal appears again as the next item to review.

**Pressing `u` again** (if you rejected two in a row) undoes the second-most-recent rejection.

**Pressing `u` with nothing to undo** shows: `Nothing to undo`

---

## Scenario 2 — Cross-session recovery

You quit the review session before noticing you accidentally rejected notes yesterday.

```bash
uv run python src/review_cli.py --recover-rejected
```

Output:
```
Rejected notes (last 30 days): 3 note(s)

[1] Stoic Philosophy Highlights [philosophy]  rejected: 2026-04-23
[2] Marketing Analytics Deep Dive [analytics]  rejected: 2026-04-22
[3] Book Beta [analytics]  rejected: 2026-04-21

[r] recover  [n] next  [q] quit
```

Press `r` on the notes you want to recover. They are restored to the pending review queue and will appear in your next `python src/review_cli.py` session.

---

## Scenario 3 — No accidental rejections

```bash
uv run python src/review_cli.py --recover-rejected
# → "No rejected notes in the last 30 days."
```

---

## Testing the undo manually

```bash
# Seed a note and get it to the review queue:
uv run python src/watcher.py --once data/raw/evernote/some-note.enex

# Open review, reject one, undo it:
uv run python src/review_cli.py
# Press r → enter reason → press u → note comes back
```
