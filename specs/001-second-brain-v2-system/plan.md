# Implementation Plan: Second Brain v2 — Hybrid Zettelkasten Knowledge System

**Branch**: `001-second-brain-v2-system` | **Date**: 2026-04-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-second-brain-v2-system/spec.md`

## Summary

Build a local-first personal knowledge management system that compiles 18,000+ raw
notes (Notion, Google Keep, Kindle) into a structured, cross-linked markdown wiki
via a two-phase pipeline: an automated Ollama-powered proposal engine followed by a
human verification gate. The compiled wiki is indexed in ChromaDB for semantic
search with cross-encoder re-ranking, and exposed as a read-only MCP resource for
Claude Code integration. All computation runs locally on a GPU-equipped machine via
Ollama (Qwen 3.5 9B primary). A SQLite coordinator ensures atomic commits and
deterministic recovery.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ollama (Qwen 3.5 9B), chromadb, sentence-transformers
(BAAI/bge-m3 bi-encoder + BAAI/bge-reranker-v2-m3 cross-encoder), watchdog,
rich, fastmcp, langdetect (subprocess git — gitpython not used)
**Storage**: SQLite (`db/brain.sqlite` — metadata + commit coordinator), ChromaDB
(`data/processed/chroma/` — one collection per domain), markdown files + YAML front
matter (`wiki/` — compiled pages), git (`wiki/` repo — version history)
**Testing**: pytest (unit + integration); no external service mocks — integration tests
use real SQLite and real ChromaDB instances on temp directories
**Target Platform**: Linux (primary); macOS compatible; NVIDIA GPU via CUDA (RTX 3060,
12 GB VRAM)
**Project Type**: CLI tool + background daemon (file watcher) + MCP sidecar server
**Performance Goals**: <2s single-domain query (GPU); <10s per proposal review session;
<60s daily structural lint; >70% fast-track rate after calibration
**Constraints**: Fully offline — zero external network calls; domain index ≤ 300 pages
(~3,000 tokens); Ollama timeout 60s; GPU inference only (no CPU fallback needed)
**Scale/Scope**: 18,000 raw notes → 1,100–1,750 compiled wiki pages across ~9 domains;
ChromaDB scales to 100,000+ pages; calibration sprint: first 500 notes manual-only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate Question | Status |
|-----------|--------------|--------|
| I. Human Gate | Does every new wiki page and new `[[wikilink]]` require explicit human approval? | ✅ Yes — review CLI is mandatory for `is_new_page=True` or new links; fast-track is restricted to existing-page updates only |
| II. Wiki-First Indexing | Does ChromaDB index compiled wiki pages and nothing else? | ✅ Yes — raw notes never enter ChromaDB; only `render_wiki_page()` output is upserted |
| III. Domain-Bounded Context | Is each Ollama call bounded to one domain index + one note? | ✅ Yes — `ollama_agent.py` reads `domain/index.md` only; max 300 pages per domain |
| IV. Immutable Raw Sources | Is `data/raw/` append-only throughout the pipeline? | ✅ Yes — `on_deleted` marks the note as deleted without touching the file; no component writes to `data/raw/` |
| V. Audit Trail | Are all proposals, decisions, commits, and errors persisted to `brain.sqlite`? | ✅ Yes — `proposals`, `commits`, and `errors` tables cover the full lifecycle |
| VI. Local and Private | Are all inference, embedding, and storage operations local? | ✅ Yes — Ollama (local), ChromaDB (local), SQLite (local); MCP server is localhost read-only |
| VII. Fail Visibly | Does interrupted commit detection and replay happen on startup? | ✅ Yes — `replay_unfinished_commits()` runs on startup; `errors` table catches all failures |

**All gates pass. No violations. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-second-brain-v2-system/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli-contract.md         # Review CLI keybindings + session contract
│   ├── mcp-contract.md         # MCP server resources + tools
│   ├── proposal-schema.md      # Ollama JSON output schema
│   └── lint-report-schema.md   # Structural + semantic lint output schema
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── models.py            # NoteRecord, Proposal, WikiPage, IngestJob dataclasses
├── db.py                # SQLite wrapper — all DB reads/writes, state machine
├── watcher.py           # watchdog FileSystemEventHandler + IngestJob queue
├── notion_parser.py     # Notion markdown export → NoteRecord
├── keep_parser.py       # Google Keep JSON → NoteRecord
├── kindle_parser.py     # Kindle clippings → NoteRecord (one per book)
├── gdrive_parser.py     # Google Drive Obsidian vault backup → NoteRecord
├── evernote_parser.py   # Evernote HTML export → NoteRecord
├── obsidian_parser.py   # Obsidian vault export → NoteRecord (shared core for gdrive)
├── dedup.py             # Near-duplicate detection via ChromaDB cosine similarity
├── classifier.py        # Two-stage domain classifier (keyword + centroid embedding)
├── ollama_agent.py      # Proposal engine — Qwen 3.5 9B via Ollama, think=False
├── review_cli.py        # Human gate — rich diff display + keyboard decision capture
├── commit.py            # SQLite-coordinated atomic commit, idempotent replay
├── wiki_store.py        # Read/write wiki markdown, domain index management
├── vector_store.py      # ChromaDB wrapper, bi-encoder, cross-encoder re-ranker
├── query.py             # Query pipeline — retrieval + Ollama synthesis
├── lint.py              # Two-tier lint (structural Python-only + semantic Ollama)
├── mcp_server.py        # FastMCP read-only MCP server
└── app.py               # Optional Gradio UI

wiki/                    # Separate git repository
├── domains/
│   ├── analytics/
│   │   ├── index.md
│   │   └── *.md
│   ├── philosophy/
│   │   ├── index.md
│   │   └── *.md
│   └── [other domains]/
│       ├── index.md
│       └── *.md
├── cross-links.md
└── lint/

data/
├── raw/                 # Append-only raw sources
│   ├── notion/          # Notion .md exports (flat)
│   ├── keep/            # Google Keep .json exports (flat)
│   ├── kindle/          # Kindle My Clippings.txt (one file → N books)
│   ├── gdrive/          # Google Drive Obsidian vault backup (.md, recursive)
│   ├── evernote/        # Evernote HTML exports (.html, recursive)
│   └── obsidian/        # Obsidian direct vault export (.md, recursive)
└── processed/
    └── chroma/          # ChromaDB persistent storage

db/
├── brain.sqlite
└── backups/

config/
├── ollama_model.txt     # "qwen3.5:9b"
├── domains.yaml         # Domain taxonomy + seed terms
└── settings.yaml        # All runtime configuration

batch_log.jsonl          # Fast-track auto-approval audit log
requirements.txt
```

**Structure Decision**: Single project layout. All source modules live directly in
`src/` — no sub-packages needed at this scale. The `wiki/` directory is a separate
git repo (not the project repo) so that wiki history is independent of code history.

## Complexity Tracking

*No constitution violations detected. This section is intentionally empty.*
