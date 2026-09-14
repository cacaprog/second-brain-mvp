# Implementation Plan: Structured Wiki Pages for Academic Papers and Articles

**Branch**: `005-article-knowledge-cards` | **Date**: 2026-04-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-article-knowledge-cards/spec.md`

## Summary

Two new raw source folders (`data/raw/articles/` for Obsidian Web Clipper markdown, `data/raw/papers/` for PDF files) feed into a new academic proposal pipeline that generates structured four-section knowledge cards (Summary, Key Findings/Arguments, Core Concepts, Open Questions/Raised) instead of the generic single-paragraph proposal. A new `note_type: article` tag enables review queue filtering. Cross-paper wikilinks (US4) reuse the existing ChromaDB index. PDF text extraction uses `pymupdf` (local, no API calls).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pymupdf` (PDF text extraction — new); existing: `rich`, `sqlite3`, `chromadb`, `sentence-transformers`, `ollama`, `pyyaml`, `watchdog`
**Storage**: SQLite `db/brain.sqlite` — new `note_type` column on `notes` table; existing wiki Markdown files extended with structured sections; no new tables
**Testing**: pytest (existing)
**Target Platform**: Linux CLI, local-only
**Project Type**: CLI pipeline — two new parsers + new Ollama prompt template; modifications to `batch_ingest.py`, `watcher.py`, `review_cli.py`, `wiki_store.py`
**Performance Goals**: PDF extraction < 5s per paper; knowledge card proposal generation within existing Ollama timeout (~60s); no regression on non-academic note throughput
**Constraints**: Fully local and offline (Constitution VI); no new network calls; `pymupdf` is the only new dependency; existing 12,000-char body limit applies to PDF extracts
**Scale/Scope**: Corpus of ~50–200 academic notes initially; grows over time as Cairo clips and downloads papers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Human Gate | ✅ PASS | All academic proposals go through the existing human gate. Fast-track eligibility rules unchanged. |
| II — Wiki-First | ✅ PASS | Knowledge cards are wiki pages — the structured sections are Markdown content within the existing wiki page format. ChromaDB indexes the committed page, not the raw note. |
| III — Domain-Bounded Context | ✅ PASS | Academic proposal prompt sends: domain index + knowledge card prompt + note body (≤ 12,000 chars). Still one domain index per call. |
| IV — Immutable Raw Sources | ✅ PASS | `data/raw/articles/` and `data/raw/papers/` are append-only. No pipeline component modifies source files. |
| V — Audit Trail | ✅ PASS | `note_type` stored on NoteRecord. All proposals, decisions, and commits recorded as before. |
| VI — Local and Private | ✅ PASS | `pymupdf` extracts locally. No external API for PDF parsing or classification. |
| VII — Fail Visibly | ✅ PASS | Image-only PDFs logged to `errors` table with clear message. Empty-section placeholders surface in review rather than silently producing thin proposals. |

**No violations. Pre-research gate: PASSED. Post-design re-check: PASSED.**

## Project Structure

### Documentation (this feature)

```text
specs/005-article-knowledge-cards/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
data/raw/
├── articles/            ← NEW: Obsidian Web Clipper markdown files
└── papers/              ← NEW: PDF research papers

src/
├── article_parser.py    ← NEW: web clip markdown parser
├── pdf_parser.py        ← NEW: PDF text extractor using pymupdf
├── ollama_agent.py      ← MODIFIED: KNOWLEDGE_CARD_PROMPT + generate_knowledge_card()
├── wiki_store.py        ← MODIFIED: render_knowledge_card() for structured sections
├── batch_ingest.py      ← MODIFIED: _source_glob() for articles/ and papers/ sources
├── watcher.py           ← MODIFIED: route article notes to card generator
├── review_cli.py        ← MODIFIED: --type filter support
└── models.py            ← MODIFIED: note_type field on NoteRecord

tests/
└── unit/
    ├── test_article_parser.py   ← NEW
    └── test_pdf_parser.py       ← NEW
```

**Structure Decision**: Two new parser modules following the exact pattern of `kindle_parser.py` and `gdrive_parser.py`. The knowledge card prompt and routing live in the existing `ollama_agent.py`. No new modules beyond the parsers — everything else is an additive extension of existing files.
