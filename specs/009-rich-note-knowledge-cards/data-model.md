# Data Model: Rich Note Knowledge Cards (009)

## No Schema Changes Required

This feature requires no new tables, no new columns, and no migrations.

## Existing Column Used: `notes.note_type`

| Column     | Table   | Type | Current Values         | New Value     |
|------------|---------|------|------------------------|---------------|
| `note_type`| `notes` | TEXT | `NULL`, `"article"`, `"paper"` | `"rich_note"` |

The `note_type` column already exists and is nullable. Setting it to `"rich_note"` for
qualifying notes requires no migration — `upsert_note()` already writes this field.

## note_type State Transitions

```
Parser runs
    │
    ├─ articles source  → note_type = "article"
    ├─ papers source    → note_type = "paper"
    └─ all others       → note_type = NULL
                                │
                          watcher.py _process_record
                                │
                          paragraph count ≥ threshold?
                                │
                    ┌───── YES ─┤─ NO ─────────────────┐
                    │           │                       │
             note_type          │               note_type stays NULL
           = "rich_note"        │               → standard proposal path
                    │           │
             knowledge card     │
               path             │
```

## Proposal Front Matter

Rich note wiki pages use `render_knowledge_card_page()` unchanged. The front matter
`note_type` field will contain `"rich_note"` (passed from `note.note_type`):

```yaml
---
slug: antifragilidade
domain: philosophy
note_type: rich_note        # ← distinguishes from article pages
languages: [pt]
created: 2026-04-25
updated: 2026-04-25
version: 1
sources: [...]
links: []
disputes: []
confidence: 0.75
---
```

## Configuration

One new key in `config/settings.yaml` under the existing `ingestion:` block:

```yaml
ingestion:
  rich_note_paragraph_threshold: 4   # integer — inclusive lower bound
```
