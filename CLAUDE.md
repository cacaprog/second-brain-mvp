# second-brain-mvp Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-25

## Active Technologies
- Python 3.11+ + langdetect, sentence-transformers (BAAI/bge-m3), PyYAML, watchdog, rich, sqlite3 (stdlib) (002-kindle-multi-domain)
- SQLite (`db/brain.sqlite`) — metadata, state machine; ChromaDB (`data/processed/chroma`) — wiki page embeddings; file-based wiki (`wiki/`) — Markdown + YAML front matter (002-kindle-multi-domain)
- Python 3.11+ + rich (existing — console output), sqlite3 stdlib (existing — undo DB writes); no new packages (004-undo-reject)
- SQLite `db/brain.sqlite` — `proposals` table (`decision`, `rejection_reason` columns) + `notes` table (`status` column) (004-undo-reject)
- Python 3.11+ + `pymupdf` (PDF text extraction — new); existing: `rich`, `sqlite3`, `chromadb`, `sentence-transformers`, `ollama`, `pyyaml`, `watchdog` (005-article-knowledge-cards)
- SQLite `db/brain.sqlite` — new `note_type` column on `notes` table; existing wiki Markdown files extended with structured sections; no new tables (005-article-knowledge-cards)
- Python 3.11+ + `yaml`, `re`, `pathlib`, `ollama` (existing); consolidation logic from `wiki_cleaner.py` (feature 006) (007-merge-slug-duplicates)
- wiki Markdown files (`wiki/domains/*/`), domain index tables (`index.md`), ChromaDB (local), SQLite `db/brain.sqlite` (`notes.wiki_page` column) (007-merge-slug-duplicates)
- Python 3.11+ + ollama, sqlite3 (stdlib), PyYAML, rich — all existing (008-smart-wiki-cleaner)
- SQLite `db/brain.sqlite` (read-only for `notes.note_type`), wiki Markdown files (008-smart-wiki-cleaner)

- Python 3.11+ + ollama (Qwen 3.5 9B), chromadb, sentence-transformers (001-second-brain-v2-system)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 008-smart-wiki-cleaner: Added Python 3.11+ + ollama, sqlite3 (stdlib), PyYAML, rich — all existing
- 007-merge-slug-duplicates: Added Python 3.11+ + `yaml`, `re`, `pathlib`, `ollama` (existing); consolidation logic from `wiki_cleaner.py` (feature 006)
- 005-article-knowledge-cards: Added Python 3.11+ + `pymupdf` (PDF text extraction — new); existing: `rich`, `sqlite3`, `chromadb`, `sentence-transformers`, `ollama`, `pyyaml`, `watchdog`


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
