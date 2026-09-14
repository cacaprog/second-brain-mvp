# Feature Specification: Smart Wiki Cleaner — Content-Aware Consolidation

**Feature Branch**: `008-smart-wiki-cleaner`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "Make wiki_cleaner smarter about when to consolidate wiki page body paragraphs. Article and paper notes must be left completely untouched. Non-article notes with 3+ paragraphs but no actual repetition should be kept as composite knowledge. Only actually repetitive paragraphs should trigger LLM consolidation."

## User Scenarios & Testing

### User Story 1 — Article and Paper Pages Are Never Touched (Priority: P1)

A user runs the cleaner over the entire wiki. Pages generated from article or paper notes — which contain structured, deep knowledge in sections like Summary, Key Findings, Core Concepts, and Open Questions — are skipped entirely, regardless of paragraph count or content similarity.

**Why this priority**: Destroying structured knowledge-card content would be the most harmful regression. This guard must be airtight before any other logic runs.

**Independent Test**: Run `python src/wiki_cleaner.py --dry-run` and confirm that every page associated with `note_type="article"` shows status `skipped (article)` and no file is modified.

**Acceptance Scenarios**:

1. **Given** a wiki page whose source notes are all typed as `article`, **When** the cleaner runs, **Then** the page is skipped and no LLM call is made.
2. **Given** an article page with 10 identical paragraphs, **When** the cleaner runs, **Then** the page is still skipped — content analysis is not applied to article pages.
3. **Given** a wiki page with mixed note types (some `article`, some `None`), **When** the cleaner runs, **Then** the page is treated as an article and skipped.

---

### User Story 2 — Non-Repetitive Pages Are Preserved as Composite Knowledge (Priority: P1)

A user runs the cleaner on a wiki page that has 4 paragraphs covering genuinely distinct aspects of a concept (layered from different ingestion rounds). The cleaner detects that no paragraph is a duplicate of another and leaves the page unchanged.

**Why this priority**: Silently collapsing rich multi-perspective content into a single paragraph is data loss. This guard ensures the cleaner only acts when there is proven redundancy.

**Independent Test**: Create or identify a wiki page with 3+ unique paragraphs (no repeated content). Run `python src/wiki_cleaner.py --path <file> --dry-run` and confirm status `skipped (no repetition)`.

**Acceptance Scenarios**:

1. **Given** a non-article page with 3 paragraphs that are all distinct, **When** the cleaner runs, **Then** the page is skipped with reason `no repetition`.
2. **Given** a non-article page with 5 unique paragraphs, **When** the cleaner runs, **Then** the page is skipped — paragraph count alone does not trigger consolidation.
3. **Given** a page with 2 paragraphs (regardless of content), **When** the cleaner runs, **Then** the page is skipped — too short to be worth consolidating.

---

### User Story 3 — Repetitive Pages Are Consolidated via LLM (Priority: P1)

A user runs the cleaner on a wiki page that accumulated repeated near-identical paragraphs across multiple ingest rounds. The cleaner detects exact-match duplicates, strips them, and if the remaining unique paragraphs still total more than two, calls the LLM to produce a single consolidated paragraph.

**Why this priority**: This is the original core capability of the cleaner — the refinements in US1 and US2 ensure it is applied precisely instead of broadly.

**Independent Test**: Run `python src/wiki_cleaner.py --path <page-with-repetition> --dry-run` and confirm the output shows the consolidated text without the duplicate paragraphs.

**Acceptance Scenarios**:

1. **Given** a page with 4 paragraphs where 2 are exact duplicates, **When** the cleaner runs, **Then** the duplicates are removed; if 2 unique paragraphs remain they are written back directly; if 3+ remain the LLM consolidates them.
2. **Given** a page with 6 paragraphs where all 6 are identical, **When** the cleaner runs, **Then** a single copy is written back without calling the LLM.
3. **Given** a page with 3 paragraphs where 1 is a duplicate of another, **When** the cleaner runs, **Then** the duplicate is removed, leaving 2 unique paragraphs written back directly (no LLM call).

---

### Edge Cases

- What happens when the database returns no notes for a wiki page slug (orphaned page)? Treat as non-article and apply normal deduplication logic.
- What happens if all paragraphs are duplicates and deduplication leaves exactly 1 paragraph? Write the single paragraph back directly; no LLM call.
- What happens when a note has `note_type=None` (unclassified)? Treat as non-article; apply deduplication logic.
- What happens when `--path` points to an article page? Skip it and report `skipped (article)`.
- What if a page body is empty after front matter extraction? Skip as before (≤2 paragraphs path).

## Requirements

### Functional Requirements

- **FR-001**: Before any content analysis, the cleaner MUST query the database to determine whether any source note linked to the wiki page has `note_type="article"`.
- **FR-002**: If any linked note has `note_type="article"`, the cleaner MUST skip the page entirely and report `skipped (article)`.
- **FR-003**: For non-article pages with more than 2 paragraphs, the cleaner MUST deduplicate paragraphs by exact match (strip whitespace, normalize case) before deciding whether to call the LLM.
- **FR-004**: If deduplication yields the same count as the original paragraph list (no duplicates found), the cleaner MUST skip the page and report `skipped (no repetition)`.
- **FR-005**: If deduplication yields 2 or fewer unique paragraphs, the cleaner MUST write those paragraphs back directly without calling the LLM.
- **FR-006**: Only when deduplication reduces the paragraph count AND the unique count exceeds 2 MUST the cleaner call the LLM to consolidate.
- **FR-007**: The `--dry-run` flag MUST suppress all file writes; it MUST still perform the DB lookup and deduplication analysis to report what would happen.
- **FR-008**: The summary output MUST distinguish between: `skipped (≤2 paragraphs)`, `skipped (article)`, `skipped (no repetition)`, `consolidated`, and `error`.

### Key Entities

- **WikiPage**: A Markdown file under `wiki/domains/{domain}/`. Has YAML front matter with `slug` and `domain` fields. Body paragraphs separated by double newlines are the unit of analysis.
- **NoteRecord**: A row in the `notes` SQLite table. Has `wiki_page` (slug) and `note_type` (`"article"` or `None`) columns linking source notes to wiki pages.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero article/paper wiki pages are modified after a full batch run.
- **SC-002**: Pages with no duplicate paragraphs produce no LLM calls and no file changes.
- **SC-003**: Pages with repeated paragraphs are consolidated correctly, with the final body containing no exact-duplicate paragraphs.
- **SC-004**: The summary output after a batch run shows all five categories so the user can distinguish why each page was left unchanged.
- **SC-005**: A full batch run over all wiki pages completes without errors when the database is accessible.

## Assumptions

- The `note_type` column exists in the `notes` table (added in feature 005) and `DB.get_notes_by_wiki_page()` is available in `src/db.py`.
- Orphaned wiki pages (no matching notes in the database) are treated as non-article pages — skipping them based on absence of data would hide bugs.
- Paragraph deduplication uses exact match (strip + lowercase), consistent with `wiki_merger.py`. Semantic similarity detection is out of scope.
- Pages with ≤2 paragraphs are still skipped before any DB lookup (fast path unchanged).
- No new Python packages are required.
