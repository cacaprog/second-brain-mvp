# Implementation Plan: Better Wiki Slugs — Concept-Based Generation & Retroactive Cleanup

**Branch**: `011-better-wiki-slugs` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-better-wiki-slugs/spec.md`

## Summary

The current slug pipeline (`ollama_agent.py::_slugify()`) truncates by raw character count, which cuts words mid-string, leaves `---` artifacts from stripped punctuation, and lets the LLM bake sentence-length or domain-name phrasing straight into the slug. This plan (1) extracts and hardens the slug-shaping logic into a shared `slug_utils.py` used by generation, and (2) adds a new `slug_migrator.py` batch tool that heuristically flags existing bad slugs across the ~627-page wiki, regenerates them with a single-page-scoped Ollama call, previews the renames, and applies them atomically (file + front matter + domain index + cross-links + database + vector store) by reusing the existing `wiki_store.rename_wiki_page()` primitive.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pyyaml`, `ollama`, `chromadb`, `rich` — all already in `pyproject.toml`; no new packages
**Storage**: SQLite `db/brain.sqlite` (`notes.wiki_page`), ChromaDB `data/processed/chroma` (one collection per domain, keyed by slug), wiki Markdown files under `wiki/domains/*/` versioned in the wiki's own git repo
**Testing**: pytest (`tests/unit/`), following the existing direct-function-call + `tmp_path` + `unittest.mock` style used in `tests/unit/test_query_exporter.py`
**Target Platform**: Local CLI, single-user machine (existing project constraint)
**Project Type**: Single project (existing `src/` + `tests/` layout — no new top-level structure)
**Performance Goals**: N/A (personal offline batch tool); migration should only call Ollama for pages a cheap heuristic flags as bad, not all ~627 pages
**Constraints**: Local-only (Ollama, no external APIs); renames must preserve wiki git file history; `domains/queries/` pages excluded entirely; migration must be safely re-runnable after interruption
**Scale/Scope**: ~627 existing wiki pages across ~20 domains today; ongoing per-note slug generation at ingestion time (unbounded)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Human Gate | Generation-time slug logic changes what string is proposed but does not change the existing human-approval flow in `review_cli.py` — every new page still requires interactive confirmation. The retroactive migration renames existing, already-approved pages rather than creating new pages or new `[[wikilinks]]`, so it falls outside the letter of this principle; the spec's required **preview mode** (report of every proposed rename before any write) serves as the human checkpoint for this bulk structural change, matching the principle's spirit. **PASS** |
| II. Wiki-First Indexing | Migration only re-keys existing ChromaDB entries (`delete_embedding` + `upsert` on already-compiled wiki content); no raw notes are indexed. **PASS** |
| III. Domain-Bounded Context | The per-page slug-regeneration prompt receives only that single page's own title/body — no domain index, no cross-page context — which is *more* bounded than the existing proposal prompt. **PASS** |
| IV. Immutable Raw Sources | Nothing under `data/raw/` is read or written by this feature. **PASS** |
| V. Audit Trail First-Class | Migration failures are logged via `db.log_error()` against a linked note when one exists; orphaned pages (no linked note, so no valid `note_id` for the `errors` table's `NOT NULL` FK) are still surfaced in the CLI summary report so nothing fails silently. **PASS** |
| VI. Local and Private | All slug regeneration calls go through the existing local `ollama.chat()` wrapper; no new external services. **PASS** |
| VII. Fail Visibly, Recover Deterministically | Migration is idempotent (re-running skips already-migrated pages by checking the wiki's own git history), and every per-page rename is its own atomic git commit via the existing `rename_wiki_page()`, so a killed run leaves the wiki in a consistent, resumable state. **PASS** |

No violations — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/011-better-wiki-slugs/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── cli.md
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── slug_utils.py        # NEW — shared slugify/word-boundary-truncate/artifact-cleanup/
│                         #       placeholder-detection logic used by both generation and migration
├── slug_migrator.py     # NEW — retroactive migration CLI: `detect` (preview) / `apply`,
│                         #       modeled on the existing wiki_merger.py detect/batch pattern
├── ollama_agent.py       # MODIFIED — replace local _slugify() with slug_utils.slugify();
│                         #            tighten PROPOSAL_PROMPT against domain-name-in-slug;
│                         #            never write a placeholder page — fail visibly instead
├── db.py                 # MODIFIED — add DB.rename_wiki_page(old_slug, new_slug)
├── wiki_store.py         # UNCHANGED — reuse existing rename_wiki_page() primitive as-is
└── vector_store.py       # UNCHANGED — reuse existing upsert()/delete_embedding()

tests/unit/
├── test_slug_utils.py    # NEW — pure function tests (word-boundary truncation, artifact
│                         #       cleanup, placeholder detection), mirrors test_query_exporter.py
└── test_slug_migrator.py # NEW — heuristic-flagging and collision-handling tests over a
                          #       tmp_path fake wiki fixture
```

**Structure Decision**: Single project, no new top-level directories. This feature adds two small modules to the existing `src/` tree and follows the CLI-tool pattern already established by `wiki_merger.py` (detect/batch subcommands, `--dry-run`, WARN-and-continue per-item error handling) and `wiki_cleaner.py` (cheap heuristic gate before any LLM call).

## Complexity Tracking

*No constitution violations — not applicable.*
