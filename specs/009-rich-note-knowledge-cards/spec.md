# Feature Specification: Rich Note Knowledge Cards

**Feature Branch**: `009-rich-note-knowledge-cards`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "like with more than 3 paragraphs could have more deep and complex ideas, it would be an improvement if the system make the same of article and paper"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Long Notes Produce Structured Wiki Pages (Priority: P1)

A user has Kindle highlights, Notion notes, or Google Keep entries that span 4 or more
paragraphs — enough content to represent a developed, multi-faceted idea. Today these
notes go through the standard proposal path, which collapses everything into a single
prose summary and loses the internal structure. The user wants these rich notes to
receive the same knowledge-card treatment as article and paper sources: a structured
wiki page with clearly delineated sections rather than a flat paragraph dump.

**Why this priority**: This is the core value proposition. Without it, the feature does
not exist. All other stories are refinements of this outcome.

**Independent Test**: Run a Kindle or Notion note with 4+ paragraphs through the
pipeline. The resulting wiki page should have multiple named sections (e.g. Core Idea,
Supporting Evidence, Implications) instead of a single continuous paragraph.

**Acceptance Scenarios**:

1. **Given** a note with 4 or more distinct paragraphs, **When** the pipeline processes
   it, **Then** a knowledge-card wiki page is produced with at least two named sections
   and a structured layout matching the article/paper output format.

2. **Given** a note with 3 or fewer paragraphs, **When** the pipeline processes it,
   **Then** the standard proposal path is used unchanged — no regression.

3. **Given** a note flagged as `note_type = "article"` or `"paper"` regardless of
   paragraph count, **When** the pipeline processes it, **Then** the existing
   article/paper path is used as before — this feature does not override those.

---

### User Story 2 — Threshold Is Configurable (Priority: P2)

A user finds that 4 paragraphs is too low (producing bloated knowledge cards from thin
notes) or too high (leaving genuinely rich notes on the standard path). They want to
tune the cutoff without touching source code.

**Why this priority**: The right threshold depends on the user's corpus. Hard-coding it
produces a feature that works well for one dataset and poorly for another.

**Independent Test**: Change the paragraph threshold in `config/settings.yaml` and
re-run the pipeline on a note at the boundary. Confirm the routing changes accordingly.

**Acceptance Scenarios**:

1. **Given** `rich_note_paragraph_threshold: 5` in settings, **When** a note with 4
   paragraphs is processed, **Then** it takes the standard path (below threshold).

2. **Given** `rich_note_paragraph_threshold: 3` in settings, **When** a note with 3
   paragraphs is processed, **Then** it takes the knowledge-card path (at threshold).

---

### User Story 3 — Review Queue Clearly Identifies Rich-Note Cards (Priority: P3)

During human review, the user wants to immediately recognise that a proposal was
generated via the knowledge-card path (because it came from a rich note, not a
conventional article source) so they can apply the right judgement — e.g. being more
critical of structure since the source is highlights rather than a published paper.

**Why this priority**: Useful for review quality but the system works correctly without
it. A label in the review TUI is sufficient.

**Independent Test**: Process a rich note through the pipeline, then run
`review_cli.py`. The proposal header should show a visible indicator distinguishing
it from standard proposals and from article/paper proposals.

**Acceptance Scenarios**:

1. **Given** a proposal generated from a rich note (≥ threshold paragraphs), **When**
   the review TUI displays it, **Then** a label such as `[RICH NOTE]` appears alongside
   the source and confidence information.

2. **Given** a standard note proposal (below threshold), **When** displayed in the TUI,
   **Then** no such label appears — existing behaviour is unchanged.

---

### Edge Cases

- What happens when a note has exactly the threshold number of paragraphs? (boundary
  is inclusive — at-or-above routes to knowledge-card path)
- What happens when the knowledge-card LLM call times out for a rich note? (falls back
  to `commit_failed` status with a logged error, same as articles)
- What if a rich note's content is thin despite paragraph count (e.g. 4 one-sentence
  paragraphs)? (knowledge-card path still applies — the LLM produces a leaner card)
- What if a note crosses the threshold only after a version bump (re-ingest)? (the new
  version is re-routed correctly on reprocessing)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST count the number of distinct paragraphs in a note body
  before routing it to a proposal generation path.
- **FR-002**: Notes with a paragraph count at or above the configured threshold MUST be
  routed to the knowledge-card generation path, regardless of source type (kindle,
  notion, keep, gdrive, evernote).
- **FR-003**: Notes with a paragraph count below the threshold MUST continue through the
  existing standard proposal path with no change in behaviour.
- **FR-004**: Notes whose `note_type` is `"article"` or `"paper"` MUST continue to use
  their existing dedicated paths regardless of paragraph count — this feature MUST NOT
  alter their routing.
- **FR-005**: The paragraph threshold MUST be configurable in `config/settings.yaml`
  under a dedicated key, with a default value of 4.
- **FR-006**: The knowledge-card generation path for rich notes MUST produce a wiki page
  in the same structured format as article knowledge cards.
- **FR-007**: The review TUI MUST display a `[RICH NOTE]` label for proposals generated
  via this path so reviewers can distinguish them from standard and article proposals.
- **FR-008**: All pipeline error handling (timeout, empty output, JSON parse failure)
  MUST behave identically to the article knowledge-card path for rich notes.

### Key Entities

- **Rich Note**: A `NoteRecord` of any source type (kindle, notion, keep, gdrive,
  evernote) whose body contains a paragraph count at or above the configured threshold
  and whose `note_type` is not `"article"` or `"paper"`.
- **Paragraph Threshold**: An integer setting in `config/settings.yaml` that determines
  when a note qualifies as a rich note. Default: 4.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of notes with paragraph count ≥ threshold (and not already typed as
  article/paper) produce a structured knowledge-card wiki page — zero are silently
  routed to the standard path.
- **SC-002**: 100% of notes with paragraph count below threshold continue on the
  standard path — zero regressions in existing behaviour.
- **SC-003**: Changing the threshold value in settings takes effect on the next pipeline
  run with no code change required.
- **SC-004**: The `[RICH NOTE]` label appears on every rich-note proposal and on no
  standard or article proposals in the review TUI.
- **SC-005**: Rich note processing does not increase the `commit_failed` rate beyond the
  current baseline for article knowledge cards.

## Assumptions

- Paragraph counting uses the same splitting logic already present in `wiki_cleaner.py`
  (`_extract_heading_and_paragraphs`): split on double newlines, filter empty strings.
  This keeps counting consistent across the system.
- The knowledge-card template used for rich notes is identical to the one used for
  articles; no new template is needed for v1.
- `note_type` is set upstream by the parser and is not modified by this feature.
- The feature applies only to notes processed after deployment; existing `classified`
  or `commit_failed` notes are not retroactively re-routed without explicit re-ingestion.
- Word count alone is not used as a proxy for richness; paragraph structure is the
  signal, consistent with the user's description.
