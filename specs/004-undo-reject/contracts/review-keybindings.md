# Contract: Review CLI Keybindings

**Scope**: `src/review_cli.py` — interactive review session (`run_review()`)

## Existing keybindings (unchanged)

| Key | Action |
|-----|--------|
| `a` | Approve and commit |
| `e` | Edit in `$EDITOR` then approve |
| `f` | Fast-track (manual override) |
| `r` | Reject with reason |
| `s` | Skip — defer to end of session |
| `d` | Reassign to a different domain |
| `b` | Batch-approve all remaining fast-track proposals |
| `q` | Quit session |
| `?` | Show help panel |

## New keybinding (this feature)

| Key | Action | Availability | Behavior when stack is empty |
|-----|--------|-------------|------------------------------|
| `u` | Undo last rejection | Anytime during session | Prints "Nothing to undo" — no error |

## `--recover-rejected` mode (new CLI flag)

**Invocation**: `python src/review_cli.py --recover-rejected`

**Display**: Numbered list of notes rejected within the last 30 days, showing title, domain, and rejection date.

**Keybindings in recovery mode**:

| Key | Action |
|-----|--------|
| `r` | Recover (restore to pending review) |
| `n` | Next entry |
| `q` | Quit recovery mode |

## Help panel (`?`) — updated text

```
[a] Approve and commit
[e] Edit in $EDITOR then approve
[f] Fast-track this proposal (manual override)
[r] Reject with reason
[u] Undo last rejection (this session only)
[s] Skip — defer to end of session
[d] Reassign to a different domain
[b] Batch-approve all remaining fast-track proposals
[q] Quit session
```
