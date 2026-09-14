# Feature Specification: Better Wiki Slugs — Concept-Based Generation & Retroactive Cleanup

**Feature Branch**: `011-better-wiki-slugs`
**Created**: 2026-07-21
**Status**: Draft
**Input**: User description: "I want the syster for better slug. You can check the previous notes that I modified, understand how the best slug is for the notes and adjust it on the system"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Notes Get Concept-Based Slugs (Priority: P1)

When a note is ingested and filed into the wiki, the resulting page's slug is a short label naming the note's core concept — the way a person would title an index entry — instead of a truncated or paraphrased fragment of the source title or content.

**Why this priority**: Every other part of this feature builds on this rule. Fixing existing pages without fixing generation would just recreate the same mess on the next ingest run.

**Independent Test**: Ingest a batch of notes whose titles are long, punctuation-heavy, or instruction-like, and confirm every resulting wiki page slug is a short, readable concept phrase with no truncation artifacts.

**Acceptance Scenarios**:

1. **Given** a note whose title is a long sentence (e.g. "Sprint: How to Solve Big Problems and Test New Ideas in Just Five Days"), **When** the note is filed into the wiki, **Then** the slug is a short concept phrase (e.g. `sprint-methodology`), not a string truncated mid-word (e.g. `sprint-how-to-solve-big-problems-and-tes`).
2. **Given** a note whose title contains a colon or dash-separated subtitle (e.g. "Ciência e Fé: A Partícula de Deus"), **When** the note is filed into the wiki, **Then** the slug contains no artifact character runs (e.g. no `---`) and reads as a clean hyphenated phrase.
3. **Given** a note whose source text is itself an instruction or prompt (e.g. "Escreva um artigo com o tema..."), **When** the note is filed into the wiki, **Then** the slug reflects the note's actual subject, not the instructional phrasing.
4. **Given** the LLM's proposed slug is empty, generic, or otherwise unusable, **When** the note is filed into the wiki, **Then** the system falls back to a concept slug derived from the note title and never creates a placeholder page such as `none.md`.
5. **Given** a newly proposed slug would exactly collide with a different, unrelated page already in the same domain, **When** the note is filed into the wiki, **Then** the system produces a distinct, still-readable slug rather than appending the domain name as a suffix.

---

### User Story 2 - Existing Wiki Pages Are Re-Slugged (Priority: P2)

The user runs a migration over the entire existing wiki (~627 pages) that re-evaluates every page's slug against the new quality rules and renames pages whose slugs are poor, while updating every place that slug is referenced so nothing breaks.

**Why this priority**: The wiki accumulated a large number of pages with truncated, sentence-like, or artifact-laden slugs before this feature existed. Fixing generation alone leaves that backlog in place indefinitely.

**Independent Test**: Run the migration over the live wiki and confirm every page previously identified as having a bad slug (truncated, sentence-like, artifact-laden, or domain-suffix-duplicated) now has a concept-based slug, while pages with already-good slugs are left untouched.

**Acceptance Scenarios**:

1. **Given** an existing page with a mid-word-truncated slug (e.g. `apenas-fiquei-la-e-senti-um-turbilhao-em`), **When** the migration runs, **Then** the page is renamed to a concept-based slug and the file, front matter, domain index, database record, and vector store entry are all updated to match.
2. **Given** an existing page whose slug is already a good concept phrase (e.g. `antifragilidade`), **When** the migration runs, **Then** the page is left unchanged — no rename, no file churn.
3. **Given** other wiki pages contain in-body links pointing at a slug that gets renamed, **When** the migration runs, **Then** those links are updated to point at the new slug.
4. **Given** a page under `domains/queries/`, **When** the migration runs, **Then** the page is skipped — query result pages keep their query-derived slugs by design.
5. **Given** the migration is interrupted partway through (e.g. process killed), **When** it is run again, **Then** already-migrated pages are not reprocessed or renamed a second time, and no duplicate history entries are created.

---

### User Story 3 - Preview Before Committing to a Mass Rename (Priority: P3)

Before any existing page is renamed, the user can generate a preview report listing every page's current slug, its proposed new slug, and the reason for the change, without touching any files — so a change this broad (hundreds of renames across the whole knowledge base) can be reviewed before it's applied.

**Why this priority**: Renaming hundreds of files, database rows, and vector store entries in one pass is inherently risky. A dry-run preview is what makes User Story 2 safe to actually run.

**Independent Test**: Run the migration in preview mode and confirm a report is produced showing old slug → new slug → reason for every page, with zero files, database rows, or vector store entries modified.

**Acceptance Scenarios**:

1. **Given** the wiki has pages with both good and bad slugs, **When** the user runs the migration in preview mode, **Then** a report lists only the pages that would be renamed, each with its current slug, proposed slug, and reason.
2. **Given** a preview has been generated, **When** the user inspects the wiki repository and database afterward, **Then** nothing has changed — the preview performed no writes.
3. **Given** the user reviews the preview and applies the migration for real, **When** it completes, **Then** a final summary reports how many pages were renamed, how many were left unchanged, and how many failed (with a reason).

---

### Edge Cases

- What happens when a note's title alone doesn't yield an obviously good concept slug (very generic or ambiguous content)? The system falls back to the best available short phrase from the title rather than failing or producing a placeholder.
- What happens when the migration would rename two different pages in the same domain to the same new slug? The system must still produce a unique, readable slug for each rather than silently overwriting one page with another.
- What happens when a page's regenerated slug happens to match its current slug exactly? The page is treated as unchanged — no rename, no git churn, no re-embedding.
- What happens if two notes filed into the same domain distill to the same underlying concept (a true duplicate, not just a wording collision)? That is out of scope for this feature and remains the responsibility of the existing duplicate-merge workflow (`007-merge-slug-duplicates`).
- What happens to a page's git history when it is renamed? The rename must be recorded as a rename in the wiki git repository (preserving blame/log history), not as a delete-and-recreate.
- What happens when the migration fails partway on a single page (e.g. a write error)? That page is reported as failed with a reason, the migration continues with the remaining pages, and re-running the migration retries only the failed/unprocessed pages.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate wiki page slugs that name the note's core concept — a short, recognizable label — rather than a truncation or verbatim paraphrase of the source title or content.
- **FR-002**: The system MUST enforce a maximum slug length in words before hyphenation, so a slug is never cut off mid-word or mid-sentence by a character-count limit.
- **FR-003**: When the LLM's proposed slug is empty, a generic placeholder (e.g. "none"), or otherwise unusable, the system MUST fall back to deriving a concept slug from the note's title instead of producing an invalid or placeholder page.
- **FR-004**: The system MUST strip punctuation such as colons and dashes from source titles when building a slug without leaving leftover artifact character runs (e.g. `---`).
- **FR-005**: The system MUST NOT carry over stopword-heavy or instructional phrasing verbatim from the source text into the slug (e.g. "we-need-you-to-lead-us", "escreva-um-artigo-com-o-tema").
- **FR-006**: When a newly generated slug would collide with an existing, unrelated page's slug within the same domain, the system MUST produce a distinct, readable slug rather than appending the domain name as a disambiguating suffix.
- **FR-007**: The system MUST provide a way to re-evaluate the slug of every existing wiki page (excluding `domains/queries/`) against the rules in FR-001 through FR-006.
- **FR-008**: The system MUST support a preview mode that reports, for every page whose slug would change, the current slug, proposed slug, and reason — without modifying any file, database row, or vector store entry.
- **FR-009**: When a retroactive rename is applied, the system MUST update, per page: the file name, the `slug` field in front matter, the owning domain's `index.md` entry, the `notes.wiki_page` column for every note linked to that page, and the corresponding vector store record's identifier/metadata.
- **FR-010**: When a retroactive rename is applied, the system MUST update any in-body links in other wiki pages that reference the old slug so no link is left pointing at a slug that no longer exists.
- **FR-011**: File renames performed by the migration MUST be recorded in the wiki git repository as renames, preserving each page's file history.
- **FR-012**: The retroactive migration MUST be safely re-runnable after an interruption — pages already migrated MUST NOT be reprocessed, re-renamed, or produce duplicate history entries.
- **FR-013**: Pages under `domains/queries/` MUST be excluded from both the generation rules (FR-001–FR-006) and the retroactive migration, since their slugs are intentionally derived from query text by an existing feature.
- **FR-014**: If an existing page's regenerated slug is identical to its current slug, the system MUST leave the page untouched.
- **FR-015**: The migration MUST report a final summary of pages renamed, pages left unchanged, and pages that failed (with a reason per failure).

### Key Entities *(include if feature involves data)*

- **Wiki Page**: A Markdown file under `wiki/domains/{domain}/`, identified by its `slug` front-matter field and file name. Subject of both generation-time slug assignment and retroactive renaming.
- **Domain Index**: The `index.md` file per domain listing each page's slug and description; must stay in sync with every rename.
- **Slug Rename Mapping**: The old-slug → new-slug pairing (with reason) produced by preview mode and consumed when a rename is applied.
- **Note Record**: A row in the `notes` database table; its `wiki_page` column references a page's slug and must be updated when that page is renamed.
- **Cross-Link**: An in-body Markdown link from one wiki page to another, referencing the target's slug; must be repointed when the target is renamed.
- **Vector Embedding Record**: The vector store entry for a wiki page, keyed by slug; must be re-keyed/updated when the page is renamed so search results stay accurate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a sample of 50 newly generated slugs, none are truncated mid-word and none exceed the configured maximum word count.
- **SC-002**: Zero new wiki pages are created with placeholder slugs (e.g. `none`) going forward.
- **SC-003**: After the retroactive migration, 100% of existing non-query wiki pages have been re-evaluated, and every page previously matching a known bad-slug pattern (mid-word truncation, sentence-length slug, punctuation artifact, domain-suffix duplicate) has a concept-based slug.
- **SC-004**: After migration, 0 internal cross-links or domain index entries point to a slug that no longer exists on disk.
- **SC-005**: After migration, every wiki page's database `wiki_page` reference and vector store entry matches its current on-disk slug — no orphaned or stale references.
- **SC-006**: In a spot-check of 30 randomly renamed pages, a human reviewer judges the new slug a better representation of the page's core concept than the old one for at least 90% of the sample.
- **SC-007**: Re-running the migration after it was stopped partway completes without reprocessing already-migrated pages or producing errors on them.

## Assumptions

- No usable trail of the user's own manual slug corrections survived in the database (it has been reset since) or in the wiki's git/file-system state (no filename vs. front-matter slug mismatches were found). "Best slug" guidance in this spec is instead derived from analyzing quality patterns across the ~627 live wiki pages — contrasting good examples (e.g. `antifragilidade`, `statistical-thinking`, `nudge-choice-architecture`) against confirmed bad patterns (mid-word truncation, sentence-length slugs, punctuation artifacts, domain-suffix duplicates).
- "Concept-based" means a short label capturing the note's core idea — roughly 1 to 4 words — with no stopword-heavy phrasing and no literal sentence or instructional text, matching the wiki's own best existing examples.
- The existing LLM-based proposal step that drafts a first-pass slug during ingestion continues to run; this feature changes the rules used to validate, clean up, and fall back on that proposal, not the underlying model or ingestion flow.
- Cross-domain duplicate concepts (the same idea filed under two different domains) remain the responsibility of the existing duplicate-merge feature — this feature only fixes a slug's wording and shape, not domain-level content merging.
- The retroactive migration is a user-initiated batch operation (not an automatic background process), given the scale (~627 pages) and the risk of a mistaken mass rename.
- The wiki's git repository is treated as the source of truth for file history, so renames are expected to preserve history (equivalent to `git mv`) rather than being written as a delete followed by a new file.
