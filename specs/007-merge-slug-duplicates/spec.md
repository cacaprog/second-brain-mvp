# Feature Specification: Wiki Slug Duplicate Merger

**Feature Branch**: `007-merge-slug-duplicates`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Merge wiki pages with the same or similar slug names within a domain — detect near-duplicate page names, merge their content and metadata (sources, links, confidence), keep the canonical slug, and delete the redundant file. Also handle cross-domain duplicates: same slug appearing in multiple domains."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect and Preview All Duplicate Slugs (Priority: P1)

The user runs a detection command that scans all wiki domains and prints a full report — grouped by kind — of all duplicate situations found: (a) same-domain near-identical slugs after normalization, and (b) exact same slug appearing in two or more different domains. No files are modified.

**Why this priority**: Detection must come before any merge. The user needs to see the full picture — both kinds of duplicates — to decide which to address. This mode is also independently useful as a recurring audit tool.

**Independent Test**: Run the detect command; confirm it reports the three known same-domain pairs AND the known cross-domain slugs (e.g. `antifragilidade` in 5 domains, `resolucao-de-problemas` in 3 domains) grouped separately, and does not modify any files.

**Acceptance Scenarios**:

1. **Given** the wiki contains two pages in the same domain whose slugs normalize to the same value, **When** the detect command runs, **Then** both slugs, their domain, and their confidence scores are printed as a same-domain pair.
2. **Given** the wiki contains the same slug in multiple different domains, **When** the detect command runs, **Then** all matching pages are printed as a cross-domain group showing each domain and confidence.
3. **Given** all wiki pages have unique slugs with no near-matches, **When** the detect command runs, **Then** the output reports zero pairs found in both categories.

---

### User Story 2 - Merge a Single Near-Duplicate Pair (Priority: P1)

The user provides two page paths (or a domain + two slugs). The system merges the redundant page into the canonical one — combining sources, links, and body — then deletes the redundant file and updates the domain index to remove the stale entry.

**Why this priority**: This is the core action. The merger must be reversible via `git checkout` since it deletes a file.

**Independent Test**: Run the merge command on the `a-logica-do-consumo-verdades-e-mentiras-` / `a-logica-do-consumo-verdades-e-mentiras` pair; confirm the canonical file has both source lists merged, both link lists merged, the higher confidence value, and the redundant file is deleted.

**Acceptance Scenarios**:

1. **Given** two page paths are provided, **When** the merge command runs, **Then** the canonical page's `sources` list is the union (deduplicated) of both pages' sources.
2. **Given** two page paths are provided, **When** the merge command runs, **Then** the canonical page's `links` list is the union (deduplicated) of both pages' links.
3. **Given** two page paths are provided, **When** the merge command runs, **Then** the canonical page's `confidence` is set to the higher of the two values.
4. **Given** two page paths are provided, **When** the merge command runs, **Then** the redundant page file is deleted from disk.
5. **Given** two page paths are provided, **When** the merge command runs, **Then** the domain index no longer contains an entry for the deleted slug.
6. **Given** two page paths are provided and both have non-empty body paragraphs, **When** the merge command runs, **Then** the canonical body is consolidated using the same LLM consolidation logic as `wiki_cleaner` to avoid simple concatenation producing repetitive output.

---

### User Story 3 - Detect and Merge Cross-Domain Slug Duplicates (Priority: P2)

The wiki currently has many slugs that appear in two or more domains (e.g. `antifragilidade` in mental-model, psychology, theology, market, and philosophy). The user wants to consolidate these into a single canonical domain, merging all sources, links, and body content from the other copies.

**Why this priority**: Cross-domain duplicates are more numerous than same-domain ones and fragment knowledge across the wiki. However, the canonical domain selection requires judgment (or user override), making this slightly more complex than same-domain merging.

**Independent Test**: Run the cross-domain merge on `antifragilidade`; confirm only one copy survives (in the domain with highest confidence), its sources and links contain the union of all five copies, the other four files are deleted, and the four deleted domain indexes no longer contain `antifragilidade`.

**Acceptance Scenarios**:

1. **Given** the same slug exists in three domains, **When** the cross-domain merge runs, **Then** a single canonical page survives in the domain with the highest confidence, and the other two files are deleted.
2. **Given** the cross-domain merge runs, **When** it completes, **Then** the surviving page's `sources` and `links` are the union of all copies, deduplicated.
3. **Given** the cross-domain merge runs, **When** it completes, **Then** the surviving page's `domain` front matter field reflects its actual (canonical) domain.
4. **Given** the cross-domain merge runs, **When** it completes, **Then** each deleted page's domain index no longer lists that slug.
5. **Given** the cross-domain merge runs on pages with differing body text, **When** it completes, **Then** the body is consolidated via LLM into a single coherent summary.

---

### User Story 4 - Batch Merge All Detected Duplicates (Priority: P2)

The user runs a single command that detects and merges all duplicate situations — both same-domain near-duplicate slugs and cross-domain exact-slug duplicates — in one pass across the whole wiki.

**Why this priority**: After the detect audit confirms all pairs are genuine duplicates, the user wants to resolve everything in one operation.

**Independent Test**: Run the batch merge; confirm the number of deletions matches the number of non-canonical pages found by detect, and `git status` shows exactly the expected deleted files with zero unintended modifications.

**Acceptance Scenarios**:

1. **Given** the batch command runs, **When** it completes, **Then** no two pages in the same domain share a normalized slug.
2. **Given** the batch command runs, **When** it completes, **Then** no slug appears in more than one domain.
3. **Given** the batch command runs on any pair with different body text, **When** the merge completes, **Then** the canonical page body reflects content from all merged copies.
4. **Given** the batch command runs, **When** it completes, **Then** a summary is printed: same-domain pairs found/merged/errored, cross-domain groups found/merged/errored.

---

### Edge Cases

- What if the user specifies the redundant slug as the "canonical" one? → The system selects canonical automatically (cleaner slug for same-domain; highest confidence for cross-domain); the user can override by specifying which path to keep explicitly.
- What if both pages have identical body text? → No LLM call is needed; take one copy directly.
- What if the domain index does not contain an entry for the deleted slug? → Skip the index update step for that slug without error.
- What if a group has three or more near-identical slugs in the same domain? → Report all as a group; merge sequentially into the canonical one.
- What if the merge would leave the canonical page with zero body paragraphs? → Skip the merge, log a warning, count as errored.
- What if two cross-domain copies have the same highest confidence? → Fall back to the domain that appears first alphabetically as canonical, so the result is deterministic.
- What if a cross-domain slug group includes a page that is itself a same-domain near-duplicate? → Resolve same-domain near-duplicates first, then cross-domain; batch mode must apply them in this order.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect all pairs of pages within the same domain whose slugs normalize to the same value (normalization: strip leading/trailing dashes, collapse consecutive dashes to one).
- **FR-002**: The system MUST detect all groups of pages across different domains that share the exact same slug.
- **FR-003**: The system MUST support a detect-only mode that prints both same-domain near-duplicate pairs and cross-domain slug groups without modifying any files.
- **FR-004**: The system MUST support a merge command that accepts two or more page file paths and merges all non-canonical pages into the canonical one.
- **FR-005**: During any merge, the system MUST produce a `sources` list that is the ordered union of all merged pages' source lists, deduplicated.
- **FR-006**: During any merge, the system MUST produce a `links` list that is the ordered union of all merged pages' links lists, deduplicated.
- **FR-007**: During any merge, the system MUST set `confidence` to the highest value across all merged pages.
- **FR-008**: During any merge, the system MUST consolidate the combined body paragraphs using LLM consolidation when bodies differ; skip the LLM call when bodies are identical.
- **FR-009**: During any merge, the system MUST delete all non-canonical page files from disk.
- **FR-010**: During any merge, the system MUST remove each deleted slug's entry from its domain index file.
- **FR-011**: For same-domain merges, the canonical slug is selected by cleaner slug (no trailing punctuation, no double dashes).
- **FR-012**: For cross-domain merges, the canonical domain is the one with the highest confidence; ties broken alphabetically by domain name.
- **FR-013**: The system MUST support a batch mode that detects and merges all same-domain pairs first, then all cross-domain groups.
- **FR-014**: The system MUST print a final summary broken down by type: same-domain pairs found/merged/errored; cross-domain groups found/merged/errored.

### Key Entities

- **Same-domain near-duplicate pair**: Two pages within the same domain whose slugs produce the same value after normalization.
- **Cross-domain slug group**: Two or more pages in different domains that share the exact same slug.
- **Canonical page**: The surviving page after a merge — selected by cleaner slug (same-domain) or highest confidence (cross-domain).
- **Redundant page**: Any non-canonical page that is merged into the canonical and then deleted.
- **Normalized slug**: A slug with leading/trailing dashes stripped and consecutive dashes collapsed to one, used only for comparison — never written to disk.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a full batch merge, zero same-domain near-duplicate slug pairs remain in the wiki.
- **SC-002**: After a full batch merge, no slug appears in more than one domain.
- **SC-003**: Every merged canonical page contains the union of all merged pages' sources and links, with zero duplicates in each list.
- **SC-004**: The detect command completes a full wiki scan in under 5 seconds (no LLM calls in detect mode).
- **SC-005**: The batch merge processes all currently known same-domain pairs (3) and cross-domain groups in a single run without manual intervention.
- **SC-006**: Every deleted redundant page is recoverable via `git checkout` immediately after the merge.

## Assumptions

- The `wiki/domains/` directory structure and Markdown front matter format remain as currently implemented.
- Cross-domain pages with the same slug (e.g. `antifragilidade` in five domains) are treated as duplicates to be merged, not as intentional multi-domain placement.
- Git is the user's undo mechanism; no internal rollback is built into this tool.
- The LLM consolidation logic from `wiki_cleaner` (feature 006) can be reused or imported directly for body merging.
- The canonical page is selected algorithmically (cleaner slug for same-domain; highest confidence for cross-domain); the user does not need to specify it manually in batch mode, but can override in single-pair mode.
- Domain index entries follow the existing `| slug | description | languages |` table format in `wiki/domains/{domain}/index.md`.
- Wikilinks in other pages (e.g. `[[antifragilidade]]`) do not encode domain, so they remain valid after a cross-domain merge and require no update.
