# Contract: Review CLI `--type` Filter

**Feature**: Article Knowledge Cards (005)
**Type**: CLI contract — additive change to `review_cli.py` / `run_review()`

---

## New Flag

```
python src/review_cli.py --type <value>
```

| Argument | Type | Required | Default | Description |
|---------|------|----------|---------|-------------|
| `--type` | `str` | No | None (all types) | Filter review queue to notes with `note_type = <value>` |

### Supported values

| Value | Effect |
|-------|--------|
| `article` | Show only proposals for notes from `articles/` and `papers/` sources |
| *(any future value)* | Extensible: stored as `note_type` in DB; `--type meeting`, `--type book`, etc. work automatically |
| *(absent)* | No filter; all pending proposals shown regardless of `note_type` |

---

## Behavior contract

1. **With `--type article`**: `get_pending_proposals()` adds `AND n.note_type = 'article'` to the WHERE clause. Only proposals for article notes appear in the queue.
2. **Without `--type`**: `get_pending_proposals()` is called without the extra clause. All pending proposals appear — identical to current behavior.
3. **`--type` with an unknown value** (e.g., `--type book` before any book notes exist): Returns empty queue with message `"No pending proposals of type 'book'."` — no crash.
4. **Concurrent sessions**: If two sessions run simultaneously with different `--type` values, they see different subsets of the queue. No coordination needed — decisions are committed per-proposal.

---

## `get_pending_proposals()` signature change

```python
# Before
def get_pending_proposals(self, domain: Optional[str] = None) -> List[tuple]:

# After
def get_pending_proposals(
    self,
    domain: Optional[str] = None,
    note_type: Optional[str] = None,   # NEW
) -> List[tuple]:
```

The `note_type` parameter is forwarded from `run_review(note_type=...)`.

---

## `run_review()` signature change

```python
# Before
def run_review(domain: Optional[str] = None, days: int = 30):

# After
def run_review(
    domain: Optional[str] = None,
    days: int = 30,
    note_type: Optional[str] = None,   # NEW
):
```

---

## Existing flags (unchanged)

| Flag | Behavior |
|------|---------|
| `--domain <value>` | Filter by domain — unchanged |
| `--recover-rejected` | Cross-session undo — unchanged |
| `--days <n>` | Recovery window — unchanged |

No existing flags are modified. `--type` is purely additive.
