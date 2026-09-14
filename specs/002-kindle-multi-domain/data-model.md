# Data Model: Kindle Multi-Domain Ingest

## Entities

### Highlight (new logical entity, no new table)

Represents a single clipped passage from a Kindle book. This entity is transient — it exists in memory during parsing and is never persisted directly. It is the atomic unit of classification.

**Fields (in-memory)**:
- `text: str` — the clipped passage text
- `position: str` — Kindle position reference (extracted from metadata line, informational only)
- `book_title: str` — parent book title
- `author: str` — parent book author

**Note**: Highlights are not stored in SQLite or ChromaDB. They are grouped into HighlightGroups and then the groups become NoteRecords.

---

### HighlightGroup (new logical entity, no new table)

A collection of highlights from the same book that share the same primary domain. This is the new intermediate unit that replaces the old "all highlights per book" concatenation.

**Fields (in-memory)**:
- `book_title: str`
- `author: str`
- `domain: str` — the primary domain all highlights in this group are classified to
- `highlights: list[str]` — ordered list of highlight texts
- `body: str` — highlights joined with `\n\n---\n\n` separator (same format as current)
- `word_count: int`

**Formation rules**:
1. Every highlight is classified using keyword scoring (Stage 1 of classifier).
2. Highlights with the same primary domain are grouped together.
3. Any group with fewer than `min_group_size` highlights is merged into the group with the highest keyword overlap from the same book.
4. If only one group exists for a book, no merging is attempted (single-domain book case).

---

### NoteRecord (existing, modified)

The persisted representation of a HighlightGroup. Maps one-to-one with a row in the `notes` SQLite table.

**Changed fields**:

| Field | Old value | New value |
|---|---|---|
| `id` | `SHA-256(book_title + "\n" + body)` | `SHA-256(book_title + "\n" + domain + "\n" + body)` |
| `source_path` | `file_path#book-slug` | `file_path#book-slug#domain` |
| `title` | `book_title` | `book_title [{domain}]` (only when book produces 2+ groups) |

**Unchanged fields**: `body`, `tags` (author), `language`, `source`, `created_at`, `modified_at`, `word_count`, `version`, `domain`, `secondary_domain`, `status`, `wiki_page`.

**No schema change**: The `notes` table schema in `db.py` does not change. The new `source_path` format is purely a convention enforced by `kindle_parser.py`.

---

## DB.py Changes (new methods)

Two new methods added to the `DB` class:

### `get_notes_by_path_prefix(prefix: str) -> List[NoteRecord]`

Returns all notes whose `source_path` starts with the given prefix. Used to retrieve all records (old or new format) associated with a Kindle clippings file or a specific book.

```
prefix examples:
  "/abs/path/my_clippings.txt#"          → all records from that file
  "/abs/path/my_clippings.txt#antifrag"  → all records for Antifragile
```

### `delete_note(note_id: str) -> None`

Deletes a note record by ID. Used during migration to remove old-format single-domain records before inserting new multi-domain ones.

**Note**: Deleting a note leaves any associated proposals in the `proposals` table as orphaned rows. This is acceptable — orphaned proposals are not shown in the review CLI (they are filtered by `decision IS NULL` and the FK join). A future lint pass can identify and clean them.

---

## Settings Changes

One new section added to `config/settings.yaml`:

```yaml
kindle:
  min_group_size: 3   # minimum highlights per domain group; groups below this are merged
```

---

## Source Path Convention (updated)

| Format | Example | Meaning |
|---|---|---|
| Old (deprecated) | `…/my_clippings.txt#antifragile` | All highlights from "Antifragile", single domain |
| New | `…/my_clippings.txt#antifragile#philosophy` | Philosophy highlights from "Antifragile" |
| New | `…/my_clippings.txt#antifragile#personal-development` | Personal development highlights from "Antifragile" |

Detection of old vs. new format: old paths contain exactly one `#`; new paths contain exactly two.

---

## State Machine (no change)

The `NoteStatus` state machine and all transitions in `watcher.py` and `db.py` apply identically to each HighlightGroup's NoteRecord. Each group goes through the full pipeline independently: `pending → classified → (fast_tracked | pending_review) → committed`.
