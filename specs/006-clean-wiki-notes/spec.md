# Feature Specification: Wiki Note Body Consolidation

**Feature Branch**: `006-clean-wiki-notes`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Clean up wiki notes that have repetitive/redundant paragraphs caused by multiple ingestion rounds before domain calibration"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Batch Consolidation of Repetitive Wiki Pages (Priority: P1)

The user runs a one-time cleanup command that scans all wiki pages, identifies those whose body contains semantically redundant paragraphs (a symptom of repeated ingestion), and rewrites each body as a single coherent synthesis — preserving the front matter (slug, domain, sources, links, confidence, version) unchanged.

**Why this priority**: This is the core problem. Every affected page currently shows 4–6 near-identical paragraphs on the same topic. The wiki is unreadable until this is resolved.

**Independent Test**: Run the command on the `wiki/` directory; open a previously-affected page like `acesso-a-jesus.md` and confirm its body is now a single unified paragraph (or 2–3 clearly distinct ones) instead of 6 repetitive paragraphs.

**Acceptance Scenarios**:

1. **Given** a wiki page with 3+ body paragraphs that repeat the same concepts with minor wording variation, **When** the cleanup command runs, **Then** the page body is replaced with a single consolidated paragraph (or 2–3 clearly distinct ones) that captures the meaning without repetition.
2. **Given** a wiki page whose body is already concise and has ≤ 2 paragraphs, **When** the cleanup command runs, **Then** the page is left unchanged.
3. **Given** the cleanup command runs and modifies a page, **When** the result is inspected, **Then** all front matter fields (`slug`, `domain`, `sources`, `links`, `confidence`, `disputes`, `version`, `created`) are preserved exactly; only `updated` is bumped to today's date.

---

### User Story 2 - Dry-Run Preview Before Overwriting (Priority: P2)

The user can preview which pages would be changed and what the consolidated body would look like, without writing anything to disk, so they can verify the LLM output before committing to the change.

**Why this priority**: Destructive writes to wiki pages are hard to undo without git. A dry-run mode lets the user verify LLM quality before the real run.

**Independent Test**: Run the command with a `--dry-run` flag; confirm no files are written and the terminal shows the old and new body for each affected page.

**Acceptance Scenarios**:

1. **Given** a dry-run is requested, **When** the command completes, **Then** no wiki files are modified on disk.
2. **Given** a dry-run is requested, **When** a page is identified as needing consolidation, **Then** the terminal shows the old body and the proposed consolidated body for review.

---

### User Story 3 - Per-Page Selective Cleanup (Priority: P3)

The user can target a single wiki page by file path for cleanup, without processing the entire wiki.

**Why this priority**: After the initial batch run, individual pages may still need attention. A per-file mode avoids re-running the full batch.

**Independent Test**: Pass a single file path to the command; confirm only that file is processed and the summary reports 1 scanned.

**Acceptance Scenarios**:

1. **Given** a specific file path is provided, **When** the command runs, **Then** only that file is evaluated and potentially rewritten.
2. **Given** a path to a non-existent file is provided, **When** the command runs, **Then** an informative error message is shown and nothing is written.

---

### Edge Cases

- What happens when a page body is entirely empty after stripping the heading? → Skip the page and count as skipped.
- What happens if the LLM returns an empty or blank consolidation? → Abort the write for that page, log an error, and continue.
- What if the wiki page has no `## Sources` or `## Related` sections? → Body is the full content after the front matter; it is still processed normally.
- What if two paragraphs are genuinely distinct? → The LLM is instructed to keep distinct concepts as separate paragraphs; only true repetition is merged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST scan all wiki pages and evaluate each page's body for redundancy (paragraph count > 2 as the detection threshold).
- **FR-002**: The system MUST use the configured LLM to consolidate redundant paragraphs, not simple string deduplication.
- **FR-003**: The system MUST preserve all YAML front matter fields exactly, updating only the `updated` date on pages that are rewritten.
- **FR-004**: The system MUST support a `--dry-run` flag that prints old and new body without writing files.
- **FR-005**: The system MUST support a `--path` argument to target a single wiki file instead of the full wiki.
- **FR-006**: The system MUST skip pages whose body has ≤ 2 paragraphs.
- **FR-007**: The system MUST print a summary at the end: total scanned, changed, skipped, errored.
- **FR-008**: The system MUST abort the write for a page if the LLM response is empty, logging an error and continuing.

### Key Entities

- **Wiki Page**: A Markdown file under `wiki/domains/` with YAML front matter and a body composed of paragraphs followed by `## Sources` and `## Related` sections.
- **Body**: The portion of the wiki page between the front matter and the `## Sources` heading — the section subject to consolidation.
- **Consolidation**: An LLM-generated rewrite of the body that preserves all distinct concepts while eliminating repetitive rewording of the same idea.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All wiki pages with 3+ body paragraphs are evaluated by the cleanup command in a single run.
- **SC-002**: Pages with semantically redundant paragraphs are consolidated to 1–2 distinct paragraphs after the batch run.
- **SC-003**: Zero wiki pages have their front matter fields modified (other than `updated`) by the cleanup command.
- **SC-004**: Dry-run mode produces output for every page that would be changed, with no disk writes.
- **SC-005**: Pages with ≤ 2 body paragraphs are left untouched.

## Assumptions

- The `wiki/domains/` directory structure and Markdown format with YAML front matter remain as currently implemented.
- The configured Ollama model is capable of coherent paragraph-level synthesis in Portuguese and English.
- Git is the user's undo mechanism; no internal rollback is required from this script.
- A page with ≤ 2 body paragraphs is assumed non-repetitive and skipped without any LLM call.
- The `## Sources` and `## Related` sections are never modified by this feature.
