# Lint Report Schema

**Phase 1 output** | **Date**: 2026-04-21

Both structural and semantic lint produce JSON reports written to `wiki/lint/`.

---

## Structural Lint Report

**File**: `wiki/lint/structural-{YYYY-MM-DD}.json`

```json
{
  "generated_at": "2026-04-21T14:30:00",
  "tier": "structural",
  "summary": {
    "total_pages": 142,
    "total_issues": 5,
    "domains_checked": ["analytics", "philosophy", "data-science"]
  },
  "issues": [
    {
      "type": "orphan_page",
      "severity": "warning",
      "slug": "some-concept",
      "domain": "philosophy",
      "detail": "No inbound links in cross-links.md or any wiki page"
    },
    {
      "type": "missing_concept",
      "severity": "error",
      "slug": "nonexistent-slug",
      "domain": "analytics",
      "referenced_from": "mmm-robyn",
      "detail": "Slug referenced in links[] but no corresponding file exists"
    },
    {
      "type": "stale_page",
      "severity": "warning",
      "slug": "attribution-models",
      "domain": "analytics",
      "last_updated": "2025-10-01",
      "days_stale": 202,
      "inbound_link_count": 3,
      "detail": "Not updated in > 90 days, has 3 inbound links"
    },
    {
      "type": "deleted_source_orphan",
      "severity": "warning",
      "slug": "old-concept",
      "domain": "personal",
      "detail": "All source notes have status=deleted; wiki page may be outdated"
    },
    {
      "type": "failed_commit",
      "severity": "error",
      "commit_id": "uuid-here",
      "note_id": "sha256-here",
      "hours_unresolved": 26,
      "detail": "Commit in status=failed for > 24h"
    },
    {
      "type": "domain_over_limit",
      "severity": "error",
      "domain": "analytics",
      "page_count": 312,
      "limit": 300,
      "detail": "Domain exceeds maximum page count; split into sub-domains required"
    },
    {
      "type": "page_too_large",
      "severity": "warning",
      "slug": "machine-learning-overview",
      "domain": "data-science",
      "word_count": 2150,
      "limit": 2000,
      "detail": "Page exceeds word count ceiling; may overflow query context window"
    }
  ]
}
```

### Issue Types

| Type | Severity | Check |
|------|----------|-------|
| `orphan_page` | warning | Pages with no inbound links in cross-links.md |
| `missing_concept` | error | Slug in `links[]` with no corresponding file |
| `stale_page` | warning | `updated` > 90 days ago AND ≥ 2 inbound links |
| `low_confidence_page` | warning | All source proposals had `confidence < 0.6` |
| `deleted_source_orphan` | warning | All source notes have `status=deleted` |
| `failed_commit` | error | `commits.status=failed` unresolved > 24h |
| `domain_over_limit` | error | Domain `page_count > max_pages` |
| `page_too_large` | warning | Page word count > 2,000 |

---

## Semantic Lint Report

**File**: `wiki/lint/semantic-{YYYY-MM-DD}-{domain}.json`

```json
{
  "generated_at": "2026-04-21T14:30:00",
  "tier": "semantic",
  "domain": "philosophy",
  "model": "qwen3.5:9b",
  "lookback_days": 30,
  "pages_checked": 8,
  "summary": {
    "total_issues": 2
  },
  "issues": [
    {
      "type": "internal_contradiction",
      "slug": "stoicism",
      "domain": "philosophy",
      "statement_a": "The Stoics believed emotions should be suppressed entirely.",
      "statement_b": "Epictetus taught that emotions are natural responses to be observed, not eliminated.",
      "detail": "These two statements directly contradict each other within the same page body."
    },
    {
      "type": "unsupported_claim",
      "slug": "via-negativa",
      "domain": "philosophy",
      "claim": "Via negativa is superior to positive knowledge in all domains.",
      "detail": "Assertion has no source reference in the Sources section."
    }
  ]
}
```

### Semantic Lint Prompt

```python
SEMANTIC_LINT_PROMPT = """
Read the following wiki page and identify:
1. internal_contradictions: statements within this page that directly
   contradict each other (logical contradiction only — not differing perspectives).
2. unsupported_claims: assertions with no source reference in the Sources section.

Scope: intra-page only. Do not compare against other pages.
Return JSON only, no preamble.

Page: {slug}
Content:
{body}

{{
  "internal_contradictions": [
    {{"statement_a": "...", "statement_b": "..."}}
  ],
  "unsupported_claims": ["..."]
}}
"""
```
