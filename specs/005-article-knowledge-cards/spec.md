# Feature Specification: Structured Wiki Pages for Academic Papers and Articles

**Feature Branch**: `005-article-knowledge-cards`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: "for papers and articles, we need to think in something with summary, results, key ideas, questions... for that kind of documents, what we could do to make sense in this second brain?"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest and Structure Web-Clipped Articles (Priority: P1) 🎯 MVP

Cairo reads a web page (blog post, news article, research paper abstract, explainer) and clips it with Obsidian Web Clipper, which saves a Markdown file with metadata into a dedicated folder (`data/raw/articles/`). When this file is ingested, the system detects it as academic/article content and produces a structured knowledge card wiki page with four sections: **Summary**, **Key Arguments or Findings**, **Core Concepts**, and **Questions Raised** — instead of the generic one-paragraph proposal used for personal notes.

**Why this priority**: Web clippings are already text and require no new parser — only detection logic and a structured prompt. This is the fastest path to value and the most common source of article content in Cairo's workflow.

**Independent Test**: Save an Obsidian Web Clipper markdown file to `data/raw/articles/` and run batch ingest. Verify the resulting wiki proposal contains four distinct non-empty sections (Summary, Key Arguments/Findings, Core Concepts, Questions Raised) and that the content reflects the actual article, not a generic placeholder.

**Acceptance Scenarios**:

1. **Given** an Obsidian Web Clipper markdown file in `data/raw/articles/`, **When** it is ingested, **Then** the wiki proposal contains four structured sections with content drawn from the clipped article.
2. **Given** a clipped research article with reported results, **When** it is ingested, **Then** the Key Findings section contains the specific results or conclusions, not a restatement of the title.
3. **Given** a clipped opinion or explainer article (no empirical results), **When** it is ingested, **Then** the section is labeled "Key Arguments" and contains the author's main claims.
4. **Given** a clipped article with minimal body content (paywall truncation, stub page), **When** it is ingested, **Then** sparse sections are marked "(insufficient content — revisit source)" rather than hallucinated.
5. **Given** a non-article note from any other source (Kindle, Keep, Evernote personal note), **When** it is ingested, **Then** it uses the existing wiki format unchanged — zero regression.

---

### User Story 2 - Ingest PDF Papers into the Same Structured Format (Priority: P2)

Cairo downloads a research paper PDF and places it in `data/raw/papers/`. When batch ingest runs, the pipeline extracts the text from the PDF and produces the same four-section knowledge card as US1 — no manual copy-paste required.

**Why this priority**: PDF is the dominant format for academic papers. Without PDF support, half of Cairo's academic reading pipeline is manual. This story completes the two-source ingestion model he described.

**Independent Test**: Place a research paper PDF in `data/raw/papers/` and run batch ingest. Verify a NoteRecord is created with the paper's text as the body, and that the resulting wiki proposal contains the four structured sections with content from the actual paper.

**Acceptance Scenarios**:

1. **Given** a PDF file in `data/raw/papers/`, **When** batch ingest runs, **Then** the pipeline extracts the text, creates a NoteRecord, classifies it as academic content, and generates a four-section knowledge card proposal.
2. **Given** a multi-column academic PDF, **When** its text is extracted, **Then** the extracted text is readable and coherent enough for the LLM to identify findings and concepts (column order preserved where possible).
3. **Given** a PDF that is image-only (scanned document, no embedded text), **When** it is ingested, **Then** the system logs a clear error ("no extractable text — OCR required") and skips the file without crashing.
4. **Given** a PDF already processed in a previous run, **When** batch ingest runs again, **Then** the file is skipped (dedup) — no duplicate proposals generated.
5. **Given** a very long paper (> 12,000 characters extracted), **When** it is processed, **Then** the first 12,000 characters are used (consistent with the existing body limit) and the proposal is still generated without error.

---

### User Story 3 - Academic Notes Tagged and Filterable in the Review Queue (Priority: P3)

Academic proposals (from both web clips and PDFs) are tagged with a `note_type: article` marker. In the review CLI, Cairo can run `--type article` to show only academic proposals — letting him batch-review papers in one focused session rather than mixing them with personal notes and Kindle highlights.

**Why this priority**: Reviewing papers requires a different mental mode. Grouping them reduces context-switching and lets Cairo process a reading session's worth of clippings all at once.

**Independent Test**: Ingest 3 article notes and 3 non-article notes. Run `review_cli.py --type article`. Verify exactly 3 proposals appear. Run without `--type` and verify all 6 appear.

**Acceptance Scenarios**:

1. **Given** a note classified as academic content, **When** it enters the review queue, **Then** it is tagged `note_type: article` and appears under `--type article`.
2. **Given** a non-academic note, **When** it enters the review queue, **Then** it is NOT tagged as `article` and does NOT appear under `--type article`.
3. **Given** the review CLI is launched without `--type`, **Then** all proposals appear — existing behavior unchanged.

---

### User Story 4 - Cross-Paper Connections Surfaced as Wikilinks (Priority: P4)

When an academic wiki page is generated, the system identifies other paper pages already in the wiki that share core concepts and suggests them as `[[wikilinks]]` in the proposal. Cairo reviews these connections at the human gate before they are committed.

**Why this priority**: The real value of a second brain for academic reading is not individual summaries but the network of connections. This story makes that graph explicit and reviewable without Cairo having to recall related papers from memory.

**Independent Test**: With 5+ paper wiki pages committed, ingest a new paper whose Core Concepts overlap with 2 existing pages. Verify the proposal includes `[[wikilinks]]` to those pages in the suggested links.

**Acceptance Scenarios**:

1. **Given** existing paper wiki pages and a new paper with overlapping concepts, **When** the proposal is generated, **Then** at least one relevant `[[wikilink]]` to an existing paper page appears.
2. **Given** a paper with no conceptual overlap with existing wiki pages, **When** the proposal is generated, **Then** no spurious links are suggested.
3. **Given** Cairo rejects a suggested link during review, **Then** the committed page does not include it — human gate respected.

---

### User Story 2 - Academic Notes are Tagged and Filterable in the Review Queue (Priority: P2)

When a note is classified as academic content, it is tagged with an `article` type marker. In the review CLI, Cairo can filter the review queue to show only academic proposals — letting him batch-review papers in a single focused session rather than interleaving them with personal reflections and meeting notes.

**Why this priority**: Reviewing academic papers requires a different mental mode than reviewing personal notes. Grouping them enables focused review sessions and reduces context-switching overhead.

**Independent Test**: Ingest 3 academic notes and 3 non-academic notes. Run `review_cli.py --type article`. Verify only the 3 academic proposals appear in the queue. Run `review_cli.py` with no filter and verify all 6 appear.

**Acceptance Scenarios**:

1. **Given** a note classified as academic content, **When** it enters the review queue, **Then** it is tagged with type `article` and visible under `--type article` filtering.
2. **Given** a non-academic note, **When** it enters the review queue, **Then** it is NOT tagged as `article` and does NOT appear under `--type article` filtering.
3. **Given** the review CLI is launched without `--type`, **Then** all proposals appear regardless of type — existing behavior unchanged.

---

### User Story 3 - Cross-Paper Connections Surfaced in the Wiki Page (Priority: P3)

When a paper wiki page is generated or updated, the system identifies other papers already in the wiki that share core concepts or cite overlapping ideas and suggests them as `[[wikilinks]]` in the proposal. Cairo reviews and approves these connections, building a citation-independent knowledge graph across his reading.

**Why this priority**: The academic value of a second brain is not individual paper summaries but the network of connections between ideas. This story makes that network explicit and reviewable, rather than relying on Cairo to manually recall and link related papers.

**Independent Test**: With at least 5 paper wiki pages already committed, ingest a new paper note whose Core Concepts overlap with 2 existing pages. Verify the proposal includes `[[wikilinks]]` to those 2 existing pages in the proposal's suggested links.

**Acceptance Scenarios**:

1. **Given** existing paper wiki pages and a new paper note with overlapping core concepts, **When** the proposal is generated, **Then** at least one `[[wikilink]]` to an existing related paper appears in the proposal's suggested links.
2. **Given** a new paper with no conceptual overlap with existing wiki pages, **When** the proposal is generated, **Then** no spurious links are suggested — the links section is empty or contains only genuinely related pages.
3. **Given** Cairo rejects a suggested link during review, **Then** the committed page does not include that link — human gate is respected.

---

### Edge Cases

- A note that is partly academic (e.g., a journal entry that quotes a paper): detected as non-academic; Cairo can manually re-queue with an `article` tag if needed.
- A paper note with only a title and no body content: follows the empty-note skip rule (words=0); not processed.
- A paper note written entirely in Portuguese or another supported language: structured sections are generated in the same language as the note.
- Multiple notes about the same paper: the system detects the matching wiki page and proposes an update to existing sections rather than creating a duplicate page.
- A paper note whose findings cannot be separated from its concepts (e.g., a theoretical paper with no empirical results): Key Findings section contains the central theoretical claims; the structured format still applies.

## Requirements *(mandatory)*

### Functional Requirements

**Web Clipper Source (US1)**
- **FR-001**: The system MUST monitor a dedicated folder (`data/raw/articles/`) for Obsidian Web Clipper markdown files and route them through the academic knowledge card pipeline.
- **FR-002**: Files in `data/raw/articles/` MUST be treated as academic/article content unconditionally — no auto-detection needed; the folder is the signal.

**PDF Source (US2)**
- **FR-003**: The system MUST monitor a dedicated folder (`data/raw/papers/`) for PDF files and extract their text content to create a NoteRecord before processing.
- **FR-004**: PDFs that contain no extractable text (image-only/scanned) MUST be logged as errors with a descriptive message and skipped without crashing.
- **FR-005**: PDFs already processed in a prior run MUST be skipped on re-run (deduplication by file path, consistent with other sources).

**Structured Knowledge Card (US1 + US2)**
- **FR-006**: Every academic wiki proposal MUST contain four named sections: **Summary** (1–2 sentences), **Key Findings** or **Key Arguments** (bullet list), **Core Concepts** (central ideas), and **Open Questions** or **Questions Raised**.
- **FR-007**: Section labels MUST adapt to content type: empirical papers use "Key Findings" / "Open Questions"; opinion or review articles use "Key Arguments" / "Questions Raised."
- **FR-008**: When a section cannot be populated from the note content, the system MUST insert a placeholder ("(insufficient content — revisit source)") — it MUST NOT hallucinate content for empty sections.
- **FR-009**: Non-academic notes from all other sources (Kindle, Evernote, GDrive, Keep) MUST continue to use the existing wiki proposal format — zero regressions.

**Tagging and Filtering (US3)**
- **FR-010**: All notes originating from `data/raw/articles/` or `data/raw/papers/` MUST be stored with a `note_type: article` attribute.
- **FR-011**: The review CLI MUST accept a `--type article` flag that restricts the proposal queue to academic content only.

**Cross-Paper Links (US4)**
- **FR-012**: When generating a knowledge card, the system MUST search existing academic wiki pages for conceptual overlap and include relevant `[[wikilinks]]` in the proposal's suggested links section.
- **FR-013**: All existing proposal validation rules (confidence threshold, slug format, human gate) MUST remain unchanged.

### Key Entities

- **Knowledge Card**: A structured wiki page for academic content, with four named sections (Summary, Key Findings/Arguments, Core Concepts, Open Questions/Raised). Extends the existing wiki page format.
- **Article Note**: A NoteRecord originating from `data/raw/articles/` (web clip) or `data/raw/papers/` (PDF), tagged with `note_type: article`.
- **PDF Extract**: The raw text extracted from a PDF file, used as the body of an Article Note. Capped at 12,000 characters consistent with the existing body limit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% of web-clipped articles and PDF papers with extractable text produce wiki proposals with all four structured sections containing non-placeholder content.
- **SC-002**: Zero regressions — non-academic notes from all existing sources produce proposals in the existing format at the same rate as before this feature.
- **SC-003**: 100% of PDF files with extractable text produce a NoteRecord and a proposal on first ingest; image-only PDFs are logged as errors and skipped without crashing the pipeline.
- **SC-004**: The `--type article` filter shows only academic proposals with 100% precision (no non-academic notes leaking into the filtered list).
- **SC-005**: After 20 paper wiki pages are committed, at least 30% of new paper proposals include at least one valid cross-paper `[[wikilink]]` suggestion (US4).

## Assumptions

- Obsidian Web Clipper saves files to a specific folder that Cairo will designate as `data/raw/articles/` — the folder itself is the academic signal, no content-based detection needed.
- PDF papers are placed manually by Cairo into `data/raw/papers/` — same assumption; folder = signal.
- Most academic PDFs Cairo reads have embedded text (not scanned images). The rare image-only PDF is logged and skipped; OCR support is out of scope for this feature.
- PDF text extraction uses a local library — no external API calls, consistent with Constitution Principle VI (local and private).
- The four-section structure covers both empirical research and theoretical/review articles; label variants ("Key Arguments" vs "Key Findings") handle the distinction without requiring separate templates.
- The existing wiki page format (Markdown + YAML front matter, Obsidian-compatible) is extended with the structured sections — no format change to the container.
- Cross-paper linking (US4) uses the existing ChromaDB semantic search over committed wiki pages — no new vector index required.
- The existing 12,000-character body limit (feature 003) applies to PDF extracts; papers longer than this are truncated at the character boundary.
