# CLI Contract: Review Interface and Pipeline Commands

**Phase 1 output** | **Date**: 2026-04-21

---

## Review CLI (`review_cli.py`)

The review CLI is the human gate. It presents proposals one at a time as colored
diffs and captures keyboard decisions. Target: under 10 seconds per unambiguous
proposal.

### Session Lifecycle

```
$ python src/review_cli.py [--domain DOMAIN] [--batch-log]

1. Loads pending proposals from brain.sqlite (status=classified, not fast-tracked)
2. For each proposal (ordered by created_at ASC):
   a. Renders colored diff
   b. Waits for keypress
   c. Records decision
   d. Triggers commit or rejection
3. Exits when queue is empty or user exits
```

### Keybindings

| Key | Action | Effect |
|-----|--------|--------|
| `a` | Approve | Commit the proposal as-is |
| `e` | Approve + edit | Open `$EDITOR` with proposed content; commit on save |
| `r` | Reject | Prompt for rejection reason text; record in proposals table |
| `s` | Skip | Move proposal to end of session queue (not rejected) |
| `b` | Batch approve | Approve all remaining fast-track-eligible proposals without review |
| `q` | Quit | Exit session; all skipped proposals remain in queue |
| `?` | Help | Print keybinding reference |

### Diff Display Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Proposal  [1/12]   antifragility   philosophy   conf: 0.91
Note      notion/taleb-notes-2024-03   NEW PAGE   pt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[green]+ ## Antifragility[/green]
[green]+[/green]
[green]+ Antifragility é a propriedade de sistemas que se beneficiam...[/green]
[green]+[/green]
[green]+ ## Sources[/green]
[green]+ - [[notion/taleb-notes-2024-03]][/green]
[green]+[/green]
[green]+ ## Related[/green]
[green]+ - [[via-negativa]][/green]
[green]+ - [[optionality]][/green]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[a]pprove  [e]dit  [r]eject  [s]kip  [b]atch  [q]uit  [?]help
```

For existing pages, the diff shows changed lines only (green=added, red=removed).
For new pages, the full content is shown as additions.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Queue fully processed or user quit cleanly |
| 1 | Unhandled error during session |

---

## Ingestion CLI (`watcher.py` / pipeline entry)

```
$ python src/watcher.py                  # Start file watcher daemon
$ python src/watcher.py --once PATH      # Process a single file (no daemon)
$ python src/watcher.py --replay         # Replay unfinished commits only
```

---

## Query CLI (`query.py`)

```
$ python src/query.py "question text" [--domain DOMAIN]

Outputs:
  Answer text with [[wikilink]] citations
  Followed by: "Sources: [[slug1]], [[slug2]]"

Exit codes:
  0 — Answer found
  1 — No relevant pages found (message printed)
  2 — Ollama error
```

---

## Lint CLI (`lint.py`)

```
$ python src/lint.py --tier structural [--domain DOMAIN]
$ python src/lint.py --tier semantic --domain DOMAIN
$ python src/lint.py --after-commits N

Output: JSON report written to wiki/lint/structural-{date}.json
        or wiki/lint/semantic-{date}-{domain}.json
        Summary printed to stdout.

Exit codes:
  0 — No issues found
  1 — Issues found (details in report file)
  2 — Execution error
```

---

## Batch Log Review CLI

```
$ python src/review_cli.py --batch-log [--since DATE]

Lists all fast-tracked proposals since DATE (default: last 7 days).
For each entry: slug, confidence, model, date, git_hash.

Keybindings in batch log mode:
  [r] Revert — triggers git revert for that entry's git_hash
  [n] Next
  [q] Quit
```
