# Contract: Source Folder Conventions

**Feature**: Article Knowledge Cards (005)
**Type**: Source data contract — defines the expected structure of `data/raw/articles/` and `data/raw/papers/`

---

## `data/raw/articles/` — Obsidian Web Clipper Markdown

Files placed here are always treated as academic/article content. No content-based detection is applied.

### Expected file format

Obsidian Web Clipper saves files with optional YAML front matter followed by Markdown body:

```markdown
---
title: "Attention Is All You Need"
url: https://arxiv.org/abs/1706.03762
date: 2026-04-24
tags: [machine-learning, transformers]
---

# Attention Is All You Need

The dominant sequence transduction models are based on complex recurrent or
convolutional neural networks...
```

### Parser obligations (`article_parser.py`)

| Obligation | Detail |
|-----------|--------|
| Extract `title` | From YAML `title:` field, or from first H1 heading, or from filename |
| Extract `body` | All content after the front matter block (or full content if no front matter) |
| Extract `source_url` | From YAML `url:` field; `None` if absent |
| Extract `tags` | From YAML `tags:` field; empty list if absent |
| Set `source` | Always `"articles"` |
| Set `note_type` | Always `"article"` |
| Set `id` | SHA-256 of `body` |
| Body length | Truncate to 12,000 characters if exceeded |

### What the parser must NOT do

- Must not modify or delete the source file
- Must not fail if front matter is absent (treat entire file as body)
- Must not fail if `url:` is absent (leave `source_url` as None)
- Must not process files with empty body (0 characters after stripping)

---

## `data/raw/papers/` — PDF Research Papers

Files placed here are always treated as academic/article content.

### Expected file format

Standard PDF with embedded text (not scanned/image-only). Multi-column layouts are supported via `pymupdf` layout analysis.

### Parser obligations (`pdf_parser.py`)

| Obligation | Detail |
|-----------|--------|
| Extract text | Use `fitz.open(path)` + `page.get_text()` for all pages |
| Handle multi-column | `pymupdf` layout analysis handles column ordering automatically |
| Detect image-only | If all pages return empty/whitespace text, `is_image_only=True` |
| Image-only action | Log to `errors` table with message `"no extractable text — OCR required"` and skip |
| Extract `title` | Use `doc.metadata.get("title")` if non-empty; else use filename stem |
| Set `source` | Always `"papers"` |
| Set `note_type` | Always `"article"` |
| Set `id` | SHA-256 of extracted body text |
| Body length | Truncate to 12,000 characters if exceeded |

### What the parser must NOT do

- Must not crash on image-only PDFs — log error and return `None`
- Must not make network calls for text extraction (fully local via `pymupdf`)
- Must not fail if PDF metadata is absent

---

## Shared conventions (both sources)

- **Dedup**: Files already in the DB (same `id`) are silently skipped on re-run
- **Status flow**: Newly created `NoteRecord` enters with `status="pending"`, same as all other sources
- **Body limit**: 12,000 characters (same limit as feature 003)
- **Language detection**: Applied after text extraction, same as other sources
