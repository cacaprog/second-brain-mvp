# Contract: Knowledge Card Schema

**Feature**: Article Knowledge Cards (005)
**Type**: Output contract — defines the required structure of a knowledge card wiki page body

---

## Overview

A knowledge card is a wiki page body (Markdown string) with exactly four H2 sections. It is produced by `render_knowledge_card()` in `wiki_store.py` and passed as the `body` argument to the existing `write_wiki_page()` function. No changes to the page container format are required.

---

## Required Sections

Every knowledge card body MUST contain all four sections in this order:

| Section heading | Content type | Applies to |
|----------------|-------------|-----------|
| `## Summary` | 1–2 sentences | All articles |
| `## Key Findings` OR `## Key Arguments` | Bullet list | Empirical / Opinion |
| `## Core Concepts` | Bullet list or short paragraphs | All articles |
| `## Open Questions` OR `## Questions Raised` | Bullet list | Empirical / Opinion |

---

## Section Heading Selection

The second and fourth section headings adapt to content type:

**Empirical / research paper** (source text contains any of: `results`, `study`, `experiment`, `experiments`, `data`, `dataset`, `findings`, `methodology`, `methods`):
- Section 2: `## Key Findings`
- Section 4: `## Open Questions`

**Opinion / review / explainer** (none of the above signals present):
- Section 2: `## Key Arguments`
- Section 4: `## Questions Raised`

This detection is applied by the LLM prompt (`KNOWLEDGE_CARD_PROMPT`). The model is the final judge; the signal list is a hint in the prompt, not a post-processing rule.

---

## Placeholder Rule

If the source content is insufficient to populate a section, the model MUST write:

```
_(insufficient content — revisit source)_
```

The model MUST NOT:
- Omit a section
- Write a section heading with an empty body
- Fabricate content for an empty section

---

## Full Body Template

```markdown
## Summary

{1–2 sentences summarizing the main claim and scope of the article or paper.}

## Key Findings

- {Finding 1}
- {Finding 2}
- {Finding 3}

## Core Concepts

- **{Concept 1}**: {Brief definition or explanation.}
- **{Concept 2}**: {Brief definition or explanation.}

## Open Questions

- {Question 1}
- {Question 2}
```

Replace `## Key Findings` / `## Open Questions` with `## Key Arguments` / `## Questions Raised` for opinion articles.

---

## Suggested Links Section (US4)

When cross-paper wikilinks are found (similarity > 0.75 against existing article wiki pages), the body is extended with an optional fifth section:

```markdown
## Related Papers

- [[related-paper-slug-1]]
- [[related-paper-slug-2]]
```

This section is included in the proposal for human review. The reviewer may remove any suggested link before approving. It is NOT generated when no related pages are found.

---

## Rendering contract (`render_knowledge_card()`)

The `render_knowledge_card(body: str, related_slugs: list[str]) -> str` function in `wiki_store.py`:

| Input | Type | Description |
|-------|------|-------------|
| `body` | `str` | Raw LLM output from `generate_knowledge_card()` — already contains the four sections |
| `related_slugs` | `list[str]` | Top-3 semantically similar article page slugs (may be empty) |

| Output | Type | Description |
|--------|------|-------------|
| return value | `str` | Final wiki page body — the four LLM sections, optionally followed by `## Related Papers` |

**Responsibility split**: The LLM generates the four content sections. `render_knowledge_card()` is responsible only for appending the related papers section when `related_slugs` is non-empty. It does NOT modify the LLM section content.

---

## Compatibility

- The body string is passed directly to `write_wiki_page()` unchanged — no format conversion
- The four H2 headings are Obsidian-compatible and render correctly in Obsidian's outline view
- ChromaDB indexes the committed page body as-is — the structured sections improve semantic search quality
