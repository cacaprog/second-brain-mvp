# Feature Specification: Second Brain v2 — Hybrid Zettelkasten Knowledge System

**Feature Branch**: `001-second-brain-v2-system`
**Created**: 2026-04-21
**Status**: Draft
**Input**: User description: "based on second-brain-sdd.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Automatic Note Detection and Proposal (Priority: P1)

A user drops a new Notion export, Google Keep JSON file, or Kindle clippings file into
the raw sources directory. The system detects the file, parses it, classifies it into a
knowledge domain, checks for near-duplicates, and generates a proposal for how the note
should be integrated into the compiled wiki. The user sees the proposal appear in the
review queue without any manual trigger.

**Why this priority**: This is the entry point of the entire system. Without reliable
ingestion, no other capability functions. It is the highest-leverage automation — one
note per trigger, compounding across 18,000+ notes.

**Independent Test**: Drop a single Notion markdown file into the raw sources directory.
Verify a proposal appears in the review queue with a classified domain, a suggested wiki
page slug, a 2–3 sentence summary, and any proposed cross-references — all without
manual intervention.

**Acceptance Scenarios**:

1. **Given** a new Notion markdown file is placed in the raw sources directory,
   **When** the file watcher detects the creation event,
   **Then** a proposal appears in the review queue within 60 seconds with domain
   classification, a target wiki page slug, a summary in the note's language, and
   proposed cross-references limited to concepts already in the domain index.

2. **Given** a note is modified in the raw sources directory,
   **When** the modification is detected,
   **Then** the system generates a full updated proposal for the note and increments
   the note's version counter. (A diff view is presented in the review CLI for pages
   that already exist; patch-only proposals are not implemented.)

3. **Given** a note file is deleted from the raw sources directory,
   **When** the deletion is detected,
   **Then** the note is marked as deleted in the metadata store and no automatic
   deletion of the wiki page occurs. The corresponding wiki page is identified as a
   potential orphan during the next structural lint run (daily), not in real-time.

4. **Given** a new note has ≥ 90% similarity to an existing wiki page,
   **When** the deduplication check runs,
   **Then** the system generates a merge proposal instead of a new-page proposal, and
   presents both pages side by side for the user to decide: merge, keep existing as
   canonical, or confirm they are genuinely distinct.

---

### User Story 2 — Human Review Gate (Priority: P1)

A user opens the review CLI and sees a colored diff of a proposed wiki page change.
They can approve, edit before approving, reject with a reason, skip to the end of the
queue, or batch-approve remaining high-confidence proposals. For proposals involving
new pages or new cross-references, the gate is mandatory. For high-confidence updates
to existing pages, the user can optionally review a batch log after the fact.

**Why this priority**: The human gate is the system's primary integrity mechanism. It
prevents link hallucination — false cross-references that corrupt the associative
structure of the Zettelkasten. It shares P1 with note ingestion because neither is
useful without the other.

**Independent Test**: With a queued proposal for a new wiki page, launch the review
CLI and verify: (a) the diff is readable and correctly shows the proposed addition;
(b) pressing `a` commits the change; (c) pressing `r` with a reason rejects it and
records the reason; (d) pressing `e` opens the editor for manual refinement before
committing.

**Acceptance Scenarios**:

1. **Given** a proposal for a new wiki page is queued,
   **When** the user opens the review CLI,
   **Then** the proposal is displayed as a colored diff with the proposed page content,
   the source note summary, proposed cross-references, and confidence score.

2. **Given** the user approves a proposal,
   **When** the commit sequence completes,
   **Then** the wiki page is written, the search index is updated, cross-references are
   registered, a version history entry is created, and the note status is updated to
   committed — all as a single atomic operation.

3. **Given** a proposal meets all fast-track criteria (high confidence, no flags,
   updating an existing page only, all cross-references already in the index),
   **When** the pipeline processes the proposal,
   **Then** it is auto-approved and appended to a batch review log; the user retains the
   ability to retroactively reject any entry, which reverses the committed change.

4. **Given** a commit operation is interrupted mid-way,
   **When** the system restarts,
   **Then** it detects the incomplete commit and replays it from the beginning, producing
   the same final state as if the commit had completed uninterrupted.

---

### User Story 3 — Natural Language Query (Priority: P2)

A user asks a question in Portuguese, English, French, or Spanish. The system retrieves
the most relevant compiled wiki pages and synthesizes a coherent answer with citations
to the source wiki pages using wikilink notation. Cross-domain questions return results
from multiple domains, re-ranked by relevance.

**Why this priority**: Query is the payoff of all ingestion and compilation work. It is
P2 rather than P1 because a working query layer requires a populated wiki; the
ingestion pipeline must be stable first.

**Independent Test**: With at least 10 compiled wiki pages across 2 domains, ask a
cross-domain question in Portuguese. Verify the response cites at least 2 wiki pages
by slug, and that the answer is coherent and grounded only in the retrieved wiki pages.

**Acceptance Scenarios**:

1. **Given** the wiki contains compiled pages,
   **When** a user submits a question in any supported language,
   **Then** the system returns a synthesized answer that cites source wiki pages by slug
   and contains no information absent from the retrieved pages.

2. **Given** a question that spans multiple knowledge domains,
   **When** the query runs without a domain hint,
   **Then** results from all domains are retrieved and re-ranked by semantic relevance
   before synthesis.

3. **Given** the wiki contains no relevant pages for the question,
   **When** the query runs,
   **Then** the system explicitly states that the answer is not found in the knowledge
   base rather than fabricating an answer.

---

### User Story 4 — Wiki Integrity Maintenance (Priority: P2)

On a daily schedule (or on demand), the system scans the wiki and flags structural
problems: orphan pages with no inbound links, broken slug references, stale pages not
updated in 90+ days with multiple inbound links, pages whose source notes are all
deleted, and unresolved commit failures. Monthly, it runs a quality check on recently
modified pages to flag internal contradictions and unsupported claims within each page.

**Why this priority**: Integrity maintenance keeps the Zettelkasten trustworthy at
scale. Without it, the wiki drifts silently toward corruption as notes are updated or
deleted over time.

**Independent Test**: With at least one orphan wiki page and one page with a broken slug
reference, run the structural lint command. Verify both issues appear in the output
report with the affected page slugs identified.

**Acceptance Scenarios**:

1. **Given** the lint runs on schedule,
   **When** it completes,
   **Then** it produces a structured report listing orphan pages, broken slug references,
   stale pages, pages with deleted sources, and unresolved commit failures.

2. **Given** a monthly semantic lint runs on recently modified pages,
   **When** a page contains two directly contradictory statements,
   **Then** it is flagged in the report with the conflicting statements quoted.
   Pages with legitimately opposing perspectives are not flagged.

3. **Given** the lint reports are produced,
   **When** the user reads them,
   **Then** each issue includes enough context (page slug, issue type, relevant content)
   to act on it without opening the affected file first.

---

### User Story 5 — AI Agent Access via MCP (Priority: P3)

A user has the MCP server running alongside their Claude Code session. They can ask
Claude Code to retrieve a specific wiki page by slug, or query the knowledge base with
a question, and Claude Code transparently fetches the answer from the compiled wiki.
The MCP server never modifies the wiki.

**Why this priority**: MCP integration multiplies the value of the compiled wiki by
making it available in the AI-assisted work context. It is P3 because it depends on a
populated, stable wiki (P1 + P2 complete).

**Independent Test**: Start the MCP server with 5+ compiled wiki pages. From a Claude
Code session, request a wiki page by known slug and verify the full page content is
returned. Then submit a query and verify a synthesized response is returned.

**Acceptance Scenarios**:

1. **Given** the MCP server is running,
   **When** an agent requests a wiki page by slug,
   **Then** the full compiled page content is returned in the response.

2. **Given** the MCP server is running,
   **When** an agent submits a natural language question,
   **Then** the server returns a synthesized answer using the same query pipeline as
   the direct CLI query, with wikilink citations included.

3. **Given** an agent attempts a write operation via MCP,
   **When** the request is received,
   **Then** the server rejects it and returns an error — no writes are permitted through
   the MCP interface.

---

### Edge Cases

- What happens when the LLM times out during proposal generation? The note is logged to
  the error queue with the stage recorded; the system continues processing other notes.
- What happens when a proposed cross-reference slug does not exist in the domain index?
  Invalid links are stripped from the proposal and the confidence score is reduced
  before routing to the human gate.
- What happens when a domain exceeds its maximum page count? Structural lint flags the
  domain; the user must manually split it into sub-domains before new pages can be
  added.
- What happens when two commits attempt to update the same wiki page concurrently? The
  commit coordinator serializes commits; the second waits for the first to complete or
  fail before proceeding.
- What happens when a note is in an unsupported language? The note is processed on a
  best-effort basis using the embedding model; an unsupported-language warning is
  recorded but processing continues.
- What happens when Ollama produces malformed JSON as a proposal? The system retries
  once with a stricter prompt; on second failure the note is sent to the error queue.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect file creation, modification, and deletion events
  in the raw sources directories and enqueue them for processing automatically.
- **FR-002**: The system MUST parse notes from Notion markdown exports (`.md`),
  Google Keep JSON exports (`.json`), Kindle clippings files (`My Clippings.txt`),
  Google Drive Obsidian vault backups (`.md`, recursive), Evernote HTML exports
  (`.html`, recursive), and Obsidian vault exports (`.md`, recursive) into a
  canonical note format with title, body, tags, detected language, source type,
  and timestamps. Kindle clippings MUST produce one NoteRecord per book (not per
  file). Source type MUST be preserved (`notion`, `keep`, `kindle`, `gdrive`,
  `evernote`, `obsidian`) to enable per-source calibration metrics.
- **FR-003**: The system MUST classify each parsed note into a primary knowledge domain
  (and optionally a secondary domain) using a configurable domain taxonomy.
- **FR-004**: The system MUST check each incoming note for near-duplication against the
  existing wiki and generate a merge proposal when similarity exceeds the configured
  threshold.
- **FR-005**: The system MUST generate a structured wiki integration proposal for each
  note, including: target page slug, new/existing page flag, 2–3 sentence summary in
  the note's language, proposed cross-references limited to slugs in the domain index,
  a confidence score, and contradiction/duplicate flags.
- **FR-006**: The system MUST require explicit human approval for proposals that create
  new wiki pages or introduce new cross-references. High-confidence updates to existing
  pages with no flags and all cross-references already in the index MAY be auto-approved,
  with the decision recorded in a batch log and retroactive rejection always available.
- **FR-007**: The system MUST present proposals via a CLI review interface showing a
  colored diff, with options to approve, approve-and-edit, reject with reason, skip,
  and batch-approve eligible proposals.
- **FR-008**: The system MUST commit approved proposals atomically: writing the wiki
  page, updating the search index, registering cross-references, creating a version
  history entry, and updating the note status — such that an interrupted commit is
  detectable on restart and replayable to completion without manual intervention.
- **FR-009**: Users MUST be able to retroactively reject any auto-approved proposal,
  which MUST reverse all changes made by that proposal's commit.
- **FR-010**: The system MUST accept natural language queries in any supported language
  and return synthesized answers grounded exclusively in the compiled wiki, with
  citations to source wiki pages by slug.
- **FR-011**: Cross-domain queries MUST retrieve candidates from all domains and
  re-rank them by semantic relevance to the question before synthesis.
- **FR-012**: The system MUST run structural integrity checks on a daily schedule and
  on demand, producing a structured report of orphan pages, broken slug references,
  stale pages, orphaned-source pages, and unresolved commit failures.
- **FR-013**: The system MUST run a semantic quality check monthly on recently modified
  pages, flagging internal contradictions and unsupported claims within each page.
- **FR-014**: The system MUST expose the compiled wiki as a read-only resource via an
  MCP-compatible interface, supporting page retrieval by slug and natural language
  queries, with all write operations rejected.
- **FR-015**: The system MUST store a complete audit trail of all proposals, human
  decisions (including rejection reasons), commit outcomes, and errors in a persistent
  metadata store.
- **FR-016**: All core system operations MUST run entirely offline, with no network
  calls to external services required for ingestion, review, commit, query, or lint.
- **FR-017**: The system MUST handle note updates by generating patch proposals
  comparing the updated note against the current wiki page state.
- **FR-018**: The system MUST handle note deletions by marking the note as deleted and
  flagging any corresponding wiki pages as orphaned for human review — never
  auto-deleting wiki pages.

### Key Entities

- **Note**: A raw personal knowledge artifact from a source system (Notion, Keep,
  Kindle, Google Drive, Evernote, or Obsidian). Immutable once written to the raw
  sources directory. Carries a lifecycle status tracked from ingestion through
  commitment or rejection. The `source` field identifies the origin system for
  calibration and traceability purposes.
- **Domain**: A bounded topic shard of the knowledge base (e.g., analytics, philosophy,
  data-science). Each domain has a bounded concept index that fits within a local LLM's
  context window. Exceeding the maximum page count requires sub-domain splits.
- **Proposal**: An LLM-generated recommendation for integrating a note into the wiki.
  Contains a target concept page, a summary, proposed cross-references, a confidence
  score, and quality flags. Fast-track eligibility is determined by the pipeline, not
  the LLM.
- **Wiki Page**: A compiled, synthesized concept page with structured front matter.
  The primary knowledge artifact indexed by the search system. Maintains full version
  history. Contains: slug, domain, supported languages, source references, and
  cross-reference links.
- **Commit Record**: A record of a wiki update transaction with its status (in-progress,
  completed, failed) and all constituent operations, enabling idempotent replay on
  restart.
- **Lint Report**: A structured audit output from structural or semantic checks,
  identifying integrity issues requiring human attention, with per-issue context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can review and decide on an unambiguous proposal in under 10
  seconds on average.
- **SC-002**: The system successfully processes a corpus of 18,000+ notes with no wiki
  page containing a cross-reference that was not explicitly approved by a human or
  confirmed via the batch log review.
- **SC-003**: Single-domain queries return a synthesized answer within 2 seconds with
  GPU-accelerated inference and the full model and embedding stack loaded.
- **SC-004**: At least 70% of eligible proposals (high-confidence, existing-page
  updates) are fast-tracked, reducing total human review time to under 15 hours for
  the full 18,000-note migration.
- **SC-005**: The calibration sprint achieves a rejection rate below 15% per domain
  across the first 500 notes before automation is enabled for that domain.
- **SC-006**: Zero external network calls are made during any ingestion, review,
  commit, query, or lint operation in normal usage.
- **SC-007**: Any interrupted commit is automatically detected and recovered on system
  restart with no data loss and no manual intervention required.
- **SC-008**: Daily structural lint completes in under 60 seconds regardless of wiki
  size.
- **SC-009**: The MCP server responds to wiki page requests within 2 seconds.

## Assumptions

- The user runs the system with a GPU (NVIDIA RTX-class with ≥ 12 GB VRAM), enabling
  GPU-accelerated LLM inference and full-size embedding models without a CPU fallback.
  The low-RAM fallback embedding model is not needed for this hardware profile.
- The default LLM is Qwen 3.5 9B (thinking model; `think=False` required on all calls).
  Llama 3.1 8B is the fallback if Qwen is unavailable.
- Raw source files are exported manually from Notion, Google Keep, Kindle, Google
  Drive (Obsidian vault backup), and Evernote; no real-time sync with any of these
  services is expected in v2. The Obsidian source directory is reserved for a future
  direct vault export and is empty at the start of migration.
- The user is the sole author and sole reviewer in the human gate; there is no
  multi-user or collaborative editing use case.
- Supported note languages are Portuguese, English, French, and Spanish; notes in
  other languages are processed on a best-effort basis without guaranteed quality.
- The wiki is expected to contain 1,100–1,750 compiled concept pages from 18,000 raw
  notes (approximately 10–15× compression ratio).
- The Obsidian desktop application is available for browsing the wiki graph and
  backlinks; the system does not need to provide its own wiki reading interface.
- Mobile access and cloud sync are out of scope for v2.
- The fast-track auto-approval mechanism is disabled until the calibration sprint
  passes the 15%-rejection-rate threshold per domain.
- Domain taxonomy (initial set of domains and their seed terms) is configured manually
  before the first ingestion run and refined during the calibration sprint.
