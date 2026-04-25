# Feature Specification: Expand Note Body Limit

**Feature Branch**: `003-expand-body-limit`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: "raise the limit to 12,000 chars (option A)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Long Notes Fully Represented in Wiki (Priority: P1) 🎯 MVP

When Cairo ingests a long Evernote or Google Drive note (meeting transcripts, research dumps, long-form articles), the resulting wiki proposal reflects the full content of the document — not just the first third.

**Why this priority**: 52 Evernote notes and 26 GDrive notes are currently truncated. These are the richest, most knowledge-dense notes in the corpus. Proposals built from the first ~700 words of a 2,500-word note are systematically incomplete.

**Independent Test**: Ingest a note longer than 800 words. Verify that concepts mentioned after the 800-word mark appear in the resulting wiki proposal summary.

**Acceptance Scenarios**:

1. **Given** a 2,000-word note, **When** it is ingested, **Then** the wiki proposal summary reflects concepts from both the first and second half of the note.
2. **Given** a note shorter than 800 words, **When** it is ingested, **Then** the proposal is unchanged — no regression for short notes.
3. **Given** a note of exactly 12,000 characters, **When** it is ingested, **Then** the full content is used for proposal generation without truncation.
4. **Given** a note longer than 12,000 characters, **When** it is ingested, **Then** the first 12,000 characters are used (graceful truncation — no crash or error).

---

### Edge Cases

- Notes shorter than the old 4,000-char limit: behavior identical to before.
- Notes between 4,000 and 12,000 chars: now fully covered where previously truncated.
- Notes longer than 12,000 chars: still truncated, but at a significantly higher threshold (a ~10,000-word note would be truncated; those are rare).
- Proposal generation time may increase for long notes — acceptable as long as the Ollama timeout is not breached.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST use up to 12,000 characters of a note's body when generating a wiki proposal.
- **FR-002**: The system MUST continue to generate valid proposals for notes of any length — no new failure modes introduced.
- **FR-003**: Notes shorter than 12,000 characters MUST be sent in full with no padding or modification.
- **FR-004**: Notes longer than 12,000 characters MUST be gracefully truncated at the 12,000-character boundary without error.
- **FR-005**: All existing proposal validation rules (confidence threshold, slug format, summary quality) MUST remain unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% of previously truncated notes (those between 4,000 and 12,000 chars) produce proposals whose summaries reference content from beyond the original 4,000-character cutoff.
- **SC-002**: Zero new proposal failures or errors introduced compared to baseline failure rate.
- **SC-003**: Proposal generation time for notes under 4,000 chars remains unchanged (no regression).

## Assumptions

- Notes longer than 12,000 characters are rare in this corpus (max observed: ~15,000 chars for one outlier); a 12,000-char limit covers the vast majority without requiring chunking.
- The local LLM has sufficient context window to handle 12,000-char notes plus the domain index without quality degradation.
- Longer Ollama calls (for notes between 4,000–12,000 chars) may take 5–15 seconds longer — this is acceptable given the infrequency of such notes.
- No changes to the domain index size, prompt structure, or output format are required.
