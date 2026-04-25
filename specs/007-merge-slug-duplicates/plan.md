# Implementation Plan: Wiki Slug Duplicate Merger

**Branch**: `007-merge-slug-duplicates` | **Date**: 2026-04-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-merge-slug-duplicates/spec.md`

## Summary

Detect and merge wiki pages that share the same or near-identical slugs — either within the same domain (slug normalization duplicates) or across domains (exact-slug duplicates). The merger combines sources, links, body, and confidence from all copies into a canonical page, then deletes the redundant files, cleans up domain indexes, removes stale ChromaDB embeddings, and clears orphaned SQLite `wiki_page` references.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `yaml`, `re`, `pathlib`, `ollama` (existing); consolidation logic from `wiki_cleaner.py` (feature 006)
**Storage**: wiki Markdown files (`wiki/domains/*/`), domain index tables (`index.md`), ChromaDB (local), SQLite `db/brain.sqlite` (`notes.wiki_page` column)
**Testing**: pytest (existing)
**Target Platform**: Linux CLI, local-only
**Project Type**: CLI maintenance tool (standalone script, same pattern as `wiki_cleaner.py`)
**Performance Goals**: Detect completes in < 5 s (no LLM); merge uses one LLM call per group with differing bodies
**Constraints**: Must not touch `data/raw/`; all Ollama calls must include `think=False`; git is the sole undo mechanism
**Scale/Scope**: ~50 wiki pages today; ~3 same-domain pairs + ~20 cross-domain groups identified in current wiki

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Human Gate | PASS | Merger operates on already-approved wiki pages (post-gate artifacts), not on new proposals. No ingestion pipeline bypass. |
| II — Wiki-First Indexing | PASS (with action) | Deleted pages must have their ChromaDB embeddings removed; updated canonical must be re-upserted. Handled in implementation — see FR-009. |
| III — Domain-Bounded Context | PASS | LLM body consolidation receives only the body text of the pages being merged — no domain index loaded. Same pattern as `wiki_cleaner.py`. |
| IV — Immutable Raw Sources | PASS | Tool only modifies `wiki/` files and `db/brain.sqlite`. `data/raw/` is never touched. |
| V — Audit Trail | PASS (with action) | SQLite `notes.wiki_page` references for deleted slugs must be cleared (`NULL`). New `clear_wiki_page()` function added to `db.py`. |
| VI — Local and Private | PASS | Ollama-only; all operations local. |
| VII — Fail Visibly | PASS | Script logs per-page errors and prints a final summary. LLM failures abort the write for that group and are counted as errored. |

No constitution violations. Complexity Tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/007-merge-slug-duplicates/
├── plan.md           ← this file
├── research.md       ← Phase 0 output
├── data-model.md     ← Phase 1 output
├── contracts/
│   └── cli.md        ← Phase 1 output
└── tasks.md          ← Phase 2 output (created by /speckit.tasks)
```

### Source Code

```text
src/
├── wiki_merger.py        ← NEW: main CLI script
├── wiki_store.py         ← MODIFIED: +delete_wiki_page(), +remove_slug_from_index()
├── vector_store.py       ← MODIFIED: +delete_embedding()
├── db.py                 ← MODIFIED: +clear_wiki_page(), +get_notes_by_wiki_page()
└── wiki_cleaner.py       ← UNCHANGED: consolidation logic imported from here

tests/
└── test_wiki_merger.py   ← NEW: unit tests for detection and merge logic
```

**Structure Decision**: Single-project, same pattern as existing CLI tools (`wiki_cleaner.py`, `wiki_store.py --rename`). New functions are added to existing modules rather than creating new modules, keeping the surface area minimal.
