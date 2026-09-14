# Research: Structured Wiki Pages for Academic Papers and Articles

## Decision 1: PDF Extraction Library

**Decision**: Use `pymupdf` (import name: `fitz`, package name: `pymupdf`).

**Rationale**: Among the three candidates (`pypdf`, `pdfminer.six`, `pymupdf`), `pymupdf` is the only one with C-level layout analysis that reliably handles multi-column academic papers. It returns empty string for image-only PDFs, making detection trivial. It is fully local with no network calls (Constitution VI). Install: `uv add pymupdf`.

**Alternatives considered**:
- `pypdf` — pure Python, fast, but minimal layout awareness; garbles two-column papers into interleaved text streams
- `pdfminer.six` — good layout model but significantly slower and more complex API; no meaningful quality advantage over `pymupdf` for our use case

**Detection of image-only PDFs**: After calling `page.get_text()` on all pages, if the joined result is empty or whitespace-only, log an error and skip the file. No crash; the error is recorded in the `errors` table.

---

## Decision 2: Academic Content Detection — Folder-Based, Not Content-Based

**Decision**: Use the source folder as the signal. Files in `data/raw/articles/` are always web clips; files in `data/raw/papers/` are always PDFs. No content heuristic is needed.

**Rationale**: Cairo controls what goes into these folders. A folder-based signal is 100% precise (no false positives from GDrive notes that happen to mention "abstract") and requires zero classification logic. The alternative — detecting academic vocabulary in note text — would introduce false positives and false negatives that would require ongoing tuning.

**`note_type` value**: `"article"` for both sources. The distinction between web clip and PDF is tracked via `source` field (`"articles"` | `"papers"`), not `note_type`.

**Alternatives considered**:
- Content heuristics (detect "abstract", "methodology", "results") — rejected; imprecise, fragile across languages, requires ongoing calibration
- Filename pattern matching — rejected; less reliable than folder membership

---

## Decision 3: Knowledge Card Prompt Structure

**Decision**: A separate Ollama prompt (`KNOWLEDGE_CARD_PROMPT`) that explicitly instructs the model to produce four Markdown sections. The prompt identifies content type (research vs opinion/review) by looking for empirical signals ("results", "study", "experiment", "data") and adapts the section labels accordingly.

**Section label mapping**:
- Research paper: "## Key Findings" / "## Open Questions"
- Opinion/review/explainer: "## Key Arguments" / "## Questions Raised"

**Placeholder rule**: If a section cannot be populated, the model is instructed to write `_(insufficient content — revisit source)_` rather than fabricating content.

**Rationale**: Separating the academic prompt from the standard `PROPOSAL_PROMPT` avoids complicating the existing code path for regular notes. The standard prompt remains unchanged; `generate_knowledge_card()` is a new function that calls the new prompt.

**Alternatives considered**:
- Extend existing `PROPOSAL_PROMPT` with conditional section logic — rejected; adds complexity and risk of regressions for all note types
- Post-process standard proposal output to extract sections — rejected; fragile, dependent on model output format

---

## Decision 4: Structured Wiki Page Format

**Decision**: The knowledge card wiki page uses the same Markdown + YAML front matter format as standard pages, with the body structured into four H2 sections. This is Obsidian-compatible and requires no change to `wiki_store.write_wiki_page()` — only a new `render_knowledge_card()` function that produces the section-structured body string.

**YAML front matter additions**:
- `note_type: article` — propagated from NoteRecord
- `source_url` — extracted from Obsidian Web Clipper metadata (the `url:` field in the clipped markdown's front matter), if present

**Rationale**: Keeping the same container format means all existing tooling (Obsidian, git commit, ChromaDB indexing, structural lint) continues to work without modification. The structure lives in the body content, not the container.

---

## Decision 5: `note_type` Storage

**Decision**: Add `note_type: Optional[str]` to `NoteRecord` dataclass and a `note_type TEXT` column to the `notes` SQLite table. Default `NULL` for all existing records (treated as `"general"`). Set to `"article"` for notes from `articles/` and `papers/` sources.

**Rationale**: Storing `note_type` in the DB makes it queryable for the `--type article` review filter without needing to re-parse source files. A new column with `NULL` default requires no migration — existing rows just get `NULL`.

**Schema change**: `ALTER TABLE notes ADD COLUMN note_type TEXT;` — backwards compatible, no data loss.

**Alternatives considered**:
- Store `note_type` only in the wiki page front matter — rejected; not queryable from the review CLI without reading wiki files
- Derive from `source` field at query time — viable but requires knowing which source values map to `article`; storing explicitly is cleaner and more forward-compatible

---

## Decision 6: Cross-Paper Wikilinks (US4)

**Decision**: Reuse the existing ChromaDB semantic search over committed wiki pages. When generating a knowledge card, embed the note's Core Concepts text and query ChromaDB for the top-3 most similar existing `article`-type wiki pages. Include them as suggested links if similarity > 0.75.

**Rationale**: ChromaDB already indexes all committed wiki pages per domain. No new index is needed. The threshold of 0.75 is consistent with the existing cross-domain re-ranking threshold. Limiting to `article`-type pages avoids suggesting a Kindle highlight page as a "related paper."

**Alternatives considered**:
- Keyword overlap between Core Concepts sections — simpler but misses semantic similarity (e.g., "neural networks" and "deep learning" would not match)
- BM25 full-text search over wiki pages — rejected; ChromaDB is already in place

---

## Decision 7: `--type` Filter in Review CLI

**Decision**: Add `--type <value>` as a general filter to `run_review()` (not just `--type article`). The filter applies to the DB query in `get_pending_proposals()`, adding a `WHERE n.note_type = ?` clause when `--type` is provided.

**Rationale**: Making it general (not `--type-article`) leaves room for future note types (e.g., `meeting`, `book`) without API changes. The implementation delta is a single additional parameter to `get_pending_proposals()`.
