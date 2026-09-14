# Data Model: Wiki Slug Duplicate Merger

All entities are in-memory only (no new database tables). The tool reads from and writes to existing stores.

## PageEntry

A single wiki page as loaded for comparison.

| Field | Type | Source |
|-------|------|--------|
| `path` | `Path` | file path on disk |
| `domain` | `str` | parent directory name |
| `slug` | `str` | file stem (as written in front matter) |
| `normalized_slug` | `str` | `normalize(slug)` — for same-domain comparison only |
| `confidence` | `float` | front matter `confidence` |
| `sources` | `list[str]` | front matter `sources` |
| `links` | `list[str]` | front matter `links` |
| `languages` | `list[str]` | front matter `languages` |
| `body` | `str` | markdown body (between front matter and ## Sources) |
| `tail` | `str` | `## Sources` + `## Related` sections verbatim |
| `heading` | `str` | the `## Title` heading line |
| `meta` | `dict` | full raw front matter dict (for write-back) |

## DuplicateGroup

A set of `PageEntry` objects that should be merged into one canonical page.

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `Literal["same-domain", "cross-domain"]` | detection category |
| `pages` | `list[PageEntry]` | all pages in the group (≥ 2) |
| `canonical` | `PageEntry` | selected surviving page |
| `redundant` | `list[PageEntry]` | pages to be merged in and deleted |

**Canonical selection:**
- `same-domain`: the page whose `slug == normalized_slug` (already clean). Ties → highest confidence → alphabetical slug.
- `cross-domain`: the page with the highest `confidence`. Ties → alphabetical domain name.

## MergeOutcome

Result of processing one `DuplicateGroup`.

| Field | Type | Notes |
|-------|------|-------|
| `group` | `DuplicateGroup` | the input group |
| `status` | `Literal["merged", "skipped", "error"]` | outcome |
| `error` | `Optional[str]` | error message if status == "error" |

**Skip conditions:**
- All pages have identical normalized body text (merge would be a no-op).
- LLM returns empty string for consolidation.
- Merged body would be empty.

## State Transitions

```
DuplicateGroup
  │
  ├── dry_run=True  →  print preview, return status="merged" (no writes)
  │
  └── dry_run=False
        │
        ├── bodies identical?
        │     YES → take canonical body as-is, skip LLM
        │     NO  → call _consolidate() → get merged body
        │                │
        │                └── empty response? → status="error", abort writes
        │
        ├── write canonical page (merged front matter + merged body + tail)
        ├── delete each redundant page file
        ├── remove each redundant slug from its domain index
        ├── delete ChromaDB embedding for each redundant slug
        ├── upsert ChromaDB embedding for canonical (updated content)
        ├── clear SQLite wiki_page=NULL for each redundant slug
        └── status="merged"
```

## Front Matter Merge Rules

| Field | Merge Strategy |
|-------|---------------|
| `slug` | canonical's slug |
| `domain` | canonical's domain |
| `languages` | union, deduplicated, order preserved |
| `created` | earliest date across all pages |
| `updated` | today's date |
| `version` | canonical's version + 1 |
| `sources` | ordered union, deduplicated |
| `links` | ordered union, deduplicated |
| `disputes` | union (edge case: unlikely to have disputes on duplicates) |
| `confidence` | max across all pages |
