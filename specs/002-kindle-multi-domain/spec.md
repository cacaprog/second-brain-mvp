# Feature Specification: Kindle Multi-Domain Ingest

**Feature Branch**: `002-kindle-multi-domain`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: "Let's make the kindle ingest more precise. I have a lot of highlights on books that fit many domains. The same book -> many domains. The highlights are across all the book, not only the first 4.000 chars."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Full Coverage Across All Highlights (Priority: P1)

When Cairo ingests a Kindle clippings file, every highlight from every book is considered during processing — not just the first portion of the file. No highlight is silently dropped because it appeared too far into a large book.

**Why this priority**: The core problem. A book with 200 highlights today produces a wiki proposal built from only the first ~20 highlights. The rest of the book's knowledge is invisible to the system.

**Independent Test**: Ingest a clippings file containing a book with 100+ highlights. Verify that highlights from the second half of the book appear in the resulting wiki entries or proposals.

**Acceptance Scenarios**:

1. **Given** a book with 150 highlights, **When** the file is ingested, **Then** highlights from positions 50–150 are represented in at least one resulting wiki entry or proposal.
2. **Given** a book with highlights in positions 1–10 only about philosophy and positions 80–150 only about economics, **When** ingested, **Then** both topics produce output — neither is silently dropped.
3. **Given** a book with only 5 highlights, **When** ingested, **Then** it produces a single wiki entry as before (no regression for small books).

---

### User Story 2 - Multi-Domain Assignment Per Book (Priority: P2)

When a book's highlights span clearly distinct domains (e.g., philosophy and decision-making, or business strategy and personal finance), the system assigns each highlight group to its relevant domain rather than forcing the entire book into a single primary domain.

**Why this priority**: A book like *Thinking, Fast and Slow* touches psychology, economics, and decision-making. Today it gets filed under one domain, burying the rest. This story is what makes the second brain genuinely useful for cross-domain books.

**Independent Test**: Ingest a book whose highlights are visibly split between two domains (can be verified manually). Confirm that the system produces proposals or wiki entries for at least two distinct domains from that one book.

**Acceptance Scenarios**:

1. **Given** a book with 30 highlights about philosophy and 30 about personal development, **When** ingested, **Then** the system creates separate entries targeting both domains.
2. **Given** a book where all highlights clearly belong to one domain, **When** ingested, **Then** only one entry is created (no spurious splitting).
3. **Given** a book where a highlight is ambiguous between two domains, **When** ingested, **Then** the highlight is assigned to the domain with the strongest signal, not dropped.

---

### User Story 3 - Coherent Per-Domain Groupings (Priority: P3)

Within each domain group produced from a book, the highlights are thematically coherent — related ideas stay together, and the resulting wiki summary reflects a focused concept rather than a mix of unrelated passages.

**Why this priority**: If splitting produces incoherent groups (e.g., two unrelated highlights bundled because they both avoided the main domain), the wiki becomes noisy rather than useful. Coherence is what turns raw highlights into reusable knowledge.

**Independent Test**: Review the summaries generated for each domain group from a multi-domain book. Each summary should read as a focused statement about a concept, not a grab-bag of unrelated ideas.

**Acceptance Scenarios**:

1. **Given** a domain group from a book, **When** the wiki proposal is reviewed, **Then** the summary is coherent and concept-focused, not a concatenation of unrelated passages.
2. **Given** a highlight that belongs clearly to domain A, **When** grouped, **Then** it does not appear in the domain B group.
3. **Given** a very small group (1–2 highlights for a domain), **When** that group is too thin to warrant a standalone entry, **Then** the system either merges it into the closest match or flags it for human review rather than producing a low-quality wiki page.

---

### Edge Cases

- What happens when a book has only 1–2 highlights total? → Single entry, no splitting attempted.
- What happens when all highlights in a book are ambiguous across domains? → System picks the strongest signal domain per highlight; no highlight is dropped.
- What happens when a book generates the same domain group as a previously ingested book? → Deduplication rules apply as usual; the existing wiki page is updated or a merge proposal is queued.
- What happens when a book has 500+ highlights? → System must not time out or fail; processing may take longer but must complete.
- What happens to books already ingested under the old one-record-per-book model? → Re-ingesting the same file should replace or update existing records, not create phantom duplicates.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST process every highlight in a clippings file, regardless of how many highlights a book contains or their position in the file.
- **FR-002**: System MUST assign each highlight (or coherent group of highlights) to the domain that best matches its content.
- **FR-003**: System MUST group highlights from the same book that share the same domain into a single coherent entry for that domain.
- **FR-004**: System MUST produce separate wiki proposals for each distinct domain detected within a single book.
- **FR-005**: System MUST preserve book title and author metadata on every entry, regardless of how many domain entries are produced from that book.
- **FR-006**: System MUST NOT produce a domain entry from a group that is too thin to support a meaningful wiki summary (minimum group size applies).
- **FR-007**: System MUST handle re-ingestion of a previously processed file by updating or replacing existing records without creating duplicates.
- **FR-008**: System MUST continue to work correctly for books whose highlights all belong to a single domain (no regressions for the common case).
- **FR-009**: System MUST flag a highlight group for human review if its domain confidence falls below the existing minimum threshold.

### Key Entities

- **Highlight**: A single clipped passage from a book, with its source position and date. The atomic unit of Kindle content.
- **Highlight Group**: A collection of highlights from the same book that are assigned to the same domain. The new unit that replaces the old "one record per book" model.
- **Book**: Source of highlights, identified by title and author. One book can produce multiple Highlight Groups across different domains.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of highlights in a clippings file are represented in at least one wiki entry or proposal — zero highlights are silently dropped due to position or volume.
- **SC-002**: A book with highlights spanning 2 or more distinct domains produces at least 2 distinct wiki proposals (one per domain).
- **SC-003**: Books whose highlights belong to a single domain continue to produce exactly 1 wiki entry (no spurious fragmentation).
- **SC-004**: Re-ingesting an already-processed clippings file produces no new duplicate entries in the wiki or the pending review queue.
- **SC-005**: Each per-domain wiki proposal is coherent enough that its summary does not reference more than one unrelated concept.

## Assumptions

- A "coherent group" requires at least 3 highlights to warrant a standalone wiki entry; smaller groups are either merged with the closest matching domain group from the same book or flagged for review.
- The existing domain classification taxonomy (domains.yaml) is not being changed as part of this feature.
- Books already ingested under the old model will be re-processed when their clippings file is ingested again; the old single-domain entry will be replaced.
- Performance is a secondary concern: processing time per book may increase, but must not block the overall ingestion pipeline from completing.
- The deduplication logic remains unchanged and continues to apply to every highlight group produced.
