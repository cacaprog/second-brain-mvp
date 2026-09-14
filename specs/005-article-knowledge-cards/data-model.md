# Data Model: Article Knowledge Cards

**Phase 1 output** | **Date**: 2026-04-24 | **Branch**: `005-article-knowledge-cards`

---

## Entities

### NoteRecord (existing, modified)

One new field is added to the `NoteRecord` dataclass. All other fields are unchanged.

**New field**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `note_type` | `Optional[str]` | `None` | Content type tag. `"article"` for notes from `articles/` or `papers/` sources; `None` for all other notes (treated as `"general"`). |

**Dataclass change** (`src/models.py`):

```python
@dataclass
class NoteRecord:
    # ... existing fields unchanged ...
    note_type: Optional[str] = None   # NEW: "article" | None
```

**How it is set**: Both `article_parser.py` and `pdf_parser.py` set `note_type="article"` on the `NoteRecord` they return. All other parsers leave it `None`.

---

### Knowledge Card (logical entity, no new table)

A knowledge card is not a new database entity — it is a `NoteRecord` whose wiki proposal uses a structured four-section body instead of the generic single-paragraph format. The card lives as a `WikiPage` committed to `wiki/domains/{domain}/{slug}.md`.

**Section structure** (Markdown body):

```markdown
## Summary

_(1–2 sentences describing what the article/paper is about and its main claim.)_

## Key Findings

_(Bullet list of specific results, data points, or conclusions. For empirical papers.)_

OR

## Key Arguments

_(Bullet list of the author's main claims or positions. For opinion/review articles.)_

## Core Concepts

_(The central ideas, terms, or frameworks the work introduces or relies on.)_

## Open Questions

_(Gaps, limitations, or follow-up questions from the paper. For empirical papers.)_

OR

## Questions Raised

_(Questions the article leaves open or provokes in the reader. For opinion/review articles.)_
```

**Label selection rule**: If the source text contains empirical signals (`results`, `study`, `experiment`, `data`, `findings`), use "Key Findings" / "Open Questions". Otherwise use "Key Arguments" / "Questions Raised".

**Placeholder rule**: If a section cannot be populated, the model inserts `_(insufficient content — revisit source)_` rather than omitting the section or hallucinating content.

---

### PDF Extract (transient, in-memory)

A temporary object created by `pdf_parser.py` during text extraction. Never persisted to SQLite or ChromaDB. Converted to a `NoteRecord` before the pipeline continues.

**Fields (in-memory)**:

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Raw extracted text (≤ 12,000 characters) |
| `source_path` | `str` | Absolute path to the PDF file |
| `is_image_only` | `bool` | True if all pages returned empty text |

**Image-only detection**: After extracting text from all pages with `fitz.open()` + `page.get_text()`, if the joined result is empty or whitespace-only, `is_image_only=True` and the extract is logged to the `errors` table, not converted to a `NoteRecord`.

---

### WikiPage (existing, front matter additions)

The wiki page format is unchanged (Markdown + YAML front matter). Two fields are added to the front matter for article-type pages only.

**New front matter fields**:

| Field | Type | Presence | Description |
|-------|------|----------|-------------|
| `note_type` | `str` | Always for article pages | `"article"` — propagated from `NoteRecord.note_type` |
| `source_url` | `str\|None` | Optional | URL extracted from Obsidian Web Clipper front matter (`url:` field), if present |

**Example** (article knowledge card front matter):

```yaml
---
slug: attention-is-all-you-need
domain: machine-learning
note_type: article
source_url: https://arxiv.org/abs/1706.03762
languages: [en]
created: 2026-04-24
updated: 2026-04-24
version: 1
sources: [papers/attention-is-all-you-need.pdf]
links: [transformer-architecture, self-attention]
confidence: 0.91
---
```

---

## SQLite Schema Changes

One column is added to the existing `notes` table. No migration is required — `ALTER TABLE ADD COLUMN` with no `NOT NULL` constraint leaves existing rows with `NULL`, which the pipeline treats as `"general"`.

**Schema change** (run once at setup, idempotent on re-run):

```sql
ALTER TABLE notes ADD COLUMN note_type TEXT;
CREATE INDEX IF NOT EXISTS idx_notes_note_type ON notes(note_type);
```

**Effective schema** after change (relevant columns shown):

```sql
CREATE TABLE IF NOT EXISTS notes (
    id              TEXT PRIMARY KEY,
    source_path     TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    language        TEXT NOT NULL,
    source          TEXT NOT NULL,
    domain          TEXT,
    secondary_domain TEXT,
    note_type       TEXT,              -- NEW: "article" | NULL
    status          TEXT NOT NULL DEFAULT 'pending',
    wiki_page       TEXT,
    word_count      INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    modified_at     TEXT NOT NULL
);
```

**Query pattern for `--type article` filter**:

```sql
SELECT n.*, p.*
FROM notes n
JOIN proposals p ON p.note_id = n.id
WHERE p.decision IS NULL
  AND n.note_type = 'article'   -- added when --type article is specified
ORDER BY p.created_at;
```

---

## Source Path Conventions

| Source folder | `source` value | `note_type` value | Parser |
|--------------|---------------|------------------|--------|
| `data/raw/articles/` | `"articles"` | `"article"` | `article_parser.py` |
| `data/raw/papers/` | `"papers"` | `"article"` | `pdf_parser.py` |
| `data/raw/kindle/` | `"kindle"` | `None` | `kindle_parser.py` |
| `data/raw/gdrive/` | `"gdrive"` | `None` | `gdrive_parser.py` |
| `data/raw/obsidian/` | `"obsidian"` | `None` | `gdrive_parser.py` (shared) |

**Dedup key**: Same as all other sources — `SHA-256(body)` for the `id` field. A re-ingested article with unchanged content produces the same `id` and is skipped.

---

## Relationships (changes only)

No new tables or foreign keys. The existing relationships hold:

```
NoteRecord (1) ──── (0..N) Proposal    [unchanged]
Proposal   (1) ──── (0..1) WikiPage    [front matter gains note_type, source_url]
NoteRecord (1) ──── (0..N) ErrorRecord [image-only PDFs produce ErrorRecord entries]
```

**New logical relationship** (US4):

```
WikiPage (article) ──── (0..3) WikiPage (article)   [cross-paper wikilinks via ChromaDB search]
```

Wikilinks are suggested during proposal generation and live in `proposed_links`. They are committed as `links:` in front matter only after human approval — same as all other cross-references.
