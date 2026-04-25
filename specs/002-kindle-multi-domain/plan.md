# Implementation Plan: Kindle Multi-Domain Ingest

**Branch**: `002-kindle-multi-domain` | **Date**: 2026-04-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-kindle-multi-domain/spec.md`

## Summary

Replace the current "one NoteRecord per book" Kindle parsing model with "one NoteRecord per (book × domain) group". Each highlight is classified individually using keyword scoring. Highlights sharing the same primary domain are grouped into a single NoteRecord with a domain-scoped `source_path`. The existing classify → propose → route pipeline requires no structural changes — it operates on NoteRecords and is already multi-record-aware. The main surgery is in `kindle_parser.py` (grouping logic), `classifier.py` (expose keyword-only classify for individual highlights), and `db.py` (migration helpers).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: langdetect, sentence-transformers (BAAI/bge-m3), PyYAML, watchdog, rich, sqlite3 (stdlib)
**Storage**: SQLite (`db/brain.sqlite`) — metadata, state machine; ChromaDB (`data/processed/chroma`) — wiki page embeddings; file-based wiki (`wiki/`) — Markdown + YAML front matter
**Testing**: pytest
**Target Platform**: Linux (local), no network access
**Project Type**: CLI pipeline tool
**Performance Goals**: Per-book processing time may increase proportional to highlight count; pipeline must not time out or stall on books with 500+ highlights
**Constraints**: No external API calls; `data/raw/` is append-only; all `ollama.chat()` calls include `think=False`; domain index per LLM call must stay within ~3,000–4,000 tokens
**Scale/Scope**: Up to 500+ highlights per book; 3 Kindle clipping files currently; ~50+ notes already in DB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-design.*

| Principle | Status | Notes |
|---|---|---|
| I. Human Gate — LLM proposes, humans commit | ✓ PASS | Each HighlightGroup produces one proposal, goes through the same review/fast-track gate. No new auto-approval paths. |
| II. Wiki-First Indexing | ✓ PASS | ChromaDB still indexes compiled wiki pages only. Highlight groups are inputs to the pipeline, never indexed directly. |
| III. Domain-Bounded Context | ✓ IMPROVED | Per-domain groups are smaller than the full book concatenation. Each LLM call receives one domain index + one group's content — both well within token limits. |
| IV. Immutable Raw Sources | ✓ PASS | `data/raw/` untouched. Only derived artifacts (SQLite, wiki) change. |
| V. Audit Trail First-Class | ✓ PASS | Each HighlightGroup gets a NoteRecord with full state machine tracking. All proposals, decisions, and errors are recorded per group. |
| VI. Local and Private | ✓ PASS | No new external calls. |
| VII. Fail Visibly, Recover Deterministically | ✓ PASS | Errors per group are recorded in `errors` table individually. A failure in one group does not block other groups from the same book. |

**Result**: No violations. Complexity Tracking section not needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-kindle-multi-domain/
├── plan.md              ← this file
├── spec.md
├── research.md          ← all decisions resolved
├── data-model.md        ← entity changes and DB additions
├── quickstart.md        ← re-ingestion guide
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (files touched by this feature)

```text
src/
├── kindle_parser.py     ← major rewrite (grouping logic + per-highlight keyword classify)
├── classifier.py        ← add keyword_classify() public function
├── db.py                ← add get_notes_by_path_prefix(), delete_note()
├── batch_ingest.py      ← update _already_processed() for new source_path format
└── watcher.py           ← no change (already handles multi-record files)

config/
└── settings.yaml        ← add kindle.min_group_size: 3

tests/
├── unit/
│   ├── test_kindle_parser.py   ← new
│   └── test_classifier.py      ← extend with keyword_classify tests
└── integration/
    └── test_kindle_pipeline.py ← new end-to-end test
```

**Structure Decision**: Existing single-project layout. All changes are within `src/`. No new modules or directories required.

## Implementation Tasks

### Task 1 — Expose keyword-only classification in `classifier.py`

**File**: `src/classifier.py`
**Size**: Small (10-20 lines)

Add a public `keyword_classify(body: str, domains: dict | None = None) -> str` function that:
- Runs Stage 1 (keyword scoring) only — no embedding model load
- Accepts an optional pre-loaded `domains` dict to avoid repeated YAML reads
- Returns the domain name with the highest keyword score (or the first domain as fallback)
- Used by `kindle_parser.py` to classify individual highlights without triggering Stage 2

The existing `classify()` function is unchanged.

**Tests**: `tests/unit/test_classifier.py` — add 3-4 cases for `keyword_classify` with known domain seeds.

---

### Task 2 — Rewrite `kindle_parser.py` with per-highlight grouping

**File**: `src/kindle_parser.py`
**Size**: Medium (~80-100 lines of changed logic)

Replace the current body-concatenation approach with a grouping pipeline:

**Step 1 — Parse** (unchanged): Parse all clippings, group raw highlights by book title. Each highlight is a string of text.

**Step 2 — Classify per highlight**: For each highlight text, call `classifier.keyword_classify(highlight, domains)`. Accumulate a `dict[domain_name → list[highlight_text]]` per book.

**Step 3 — Merge thin groups**: After classifying all highlights for a book, check each domain group's size against `min_group_size` (from `settings.yaml`). Groups below the threshold are redistributed: each thin-group highlight is reassigned to the domain with the next-highest keyword score for that specific highlight. If reassignment produces only one domain for the book, that is the correct single-domain outcome.

**Step 4 — Create NoteRecords**: For each surviving domain group, create a `NoteRecord` with:
- `body`: `"\n\n---\n\n".join(group_highlights)`
- `source_path`: `f"{file_path.resolve()}#{_slugify(book_title)}#{domain}"`
- `id`: `SHA-256(f"{book_title}\n{domain}\n{body}")`
- `title`: `f"{book_title} [{domain}]"` if book has 2+ groups, else `book_title`
- `domain`: set at parse time (pre-classified)
- All other fields unchanged from current implementation

**Tests**: `tests/unit/test_kindle_parser.py` — test with synthetic clippings covering: single-domain book, two-domain book, thin groups below threshold, book with 1 highlight only.

---

### Task 3 — Add migration helpers to `db.py`

**File**: `src/db.py`
**Size**: Small (20-30 lines)

Add two methods to the `DB` class:

**`get_notes_by_path_prefix(prefix: str) -> List[NoteRecord]`**:
```sql
SELECT * FROM notes WHERE source_path LIKE ? || '%'
```
Returns all records whose `source_path` starts with `prefix`. Used to detect old-format records.

**`delete_note(note_id: str) -> None`**:
```sql
DELETE FROM notes WHERE id = ?
```
Removes a single note record. Proposals for the deleted note become orphaned (acceptable; they are not shown in the review CLI and will be cleaned by future lint).

**Tests**: Add to existing `tests/` DB tests if they exist; otherwise add inline assertions.

---

### Task 4 — Update `_already_processed` in `batch_ingest.py`

**File**: `src/batch_ingest.py`
**Size**: Small (10-15 lines)

Current logic for Kindle `.txt` files:
```python
return db.has_notes_with_path_prefix(str(file_path.resolve()) + "#")
```

New logic:
1. Retrieve all notes with prefix `str(file_path.resolve()) + "#"`.
2. If none exist → file not processed → return `False`.
3. If any note's `source_path` has exactly two `#` characters → new format → file already processed → return `True`.
4. If all notes have old format (one `#`) → migration needed:
   - Delete all old-format records for this file.
   - Return `False` so the file is re-queued.

This makes re-ingestion of old Kindle files automatic and idempotent.

**Tests**: `tests/unit/test_batch_ingest.py` or inline — test old-format detection, new-format skip, mixed-format migration path.

---

### Task 5 — Add `kindle.min_group_size` to `settings.yaml`

**File**: `config/settings.yaml`
**Size**: Trivial (2 lines)

Add under a new `kindle:` section:
```yaml
kindle:
  min_group_size: 3
```

The parser reads this via `_load_settings()` using the existing pattern used by all other modules.

---

### Task 6 — Integration test: full pipeline with multi-domain book

**File**: `tests/integration/test_kindle_pipeline.py` (new)
**Size**: Medium (~60-80 lines)

Create a synthetic `My Clippings.txt` in a temp directory with:
- Book A: 10 highlights clearly in domain X + 10 highlights clearly in domain Y
- Book B: 5 highlights all in domain X (single domain)
- Book C: 2 highlights in domain Z (below min_group_size → should merge into X or Y)

Run the full parse → group → classify path. Assert:
- Book A produces 2 NoteRecords (one per domain)
- Book B produces 1 NoteRecord
- Book C's 2 highlights are merged into the largest group from Book C (or a fallback domain)
- All NoteRecord `source_path` values follow the new `file#slug#domain` format
- No highlights are lost (total highlight count in all records = total in file)

---

### Task 7 — Re-ingest existing Kindle files

**Action**: After implementation, run:
```bash
uv run python src/batch_ingest.py --dir data/raw/kindle
```

The migration path in Task 4 handles old-format record cleanup automatically. Monitor the review queue via `review_cli.py` for new multi-domain proposals.

This task is operational, not a code change. It is the acceptance gate for SC-001 (all highlights covered) and SC-002 (multi-domain books produce multiple proposals).

## Complexity Tracking

*No constitution violations — section omitted.*
