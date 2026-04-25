# Proposal JSON Schema

**Phase 1 output** | **Date**: 2026-04-21

This is the JSON schema for the Ollama output from `ollama_agent.py`. The model is
called with `format="json"` to enforce valid JSON output.

---

## Schema

```json
{
  "summary": "string — 2 to 3 sentences, same language as the source note",
  "proposed_page": "string — lowercase-hyphenated slug",
  "is_new_page": "boolean — true if the slug does not exist in the domain index",
  "link_only": "boolean — true if note < 100 words and targets an existing page only",
  "proposed_links": ["string — slug1", "string — slug2"],
  "confidence": "float — 0.0 to 1.0",
  "flag_contradiction": "boolean",
  "flag_duplicate": "boolean"
}
```

## Field Rules

| Field | Validation | On Failure |
|-------|------------|------------|
| `summary` | Non-empty string, 1–5 sentences | Reject proposal, send to errors table |
| `proposed_page` | Matches `^[a-z0-9]+(-[a-z0-9]+)*$` | Strip and kebab-case; fail if empty |
| `is_new_page` | Boolean | Default to `True` if missing |
| `link_only` | Boolean | Default to `False` if missing |
| `proposed_links` | Array of strings; each slug checked against domain index | Strip invalid slugs; reduce confidence by 0.1 per stripped slug |
| `confidence` | Float in [0.0, 1.0] | Clamp to range; if missing default to 0.5 |
| `flag_contradiction` | Boolean | Default to `False` if missing |
| `flag_duplicate` | Boolean | Default to `False` if missing |

## Pipeline Post-Processing

After receiving the JSON from Ollama, the pipeline applies these transforms before
saving the Proposal to SQLite:

1. **Link validation**: Query domain `index.md` for each slug in `proposed_links`.
   Remove any slug not found. Apply confidence penalty (-0.1 per removed slug,
   floored at 0.0).
2. **Minimum confidence gate**: If `confidence < 0.5` (from `settings.yaml`), send
   to errors table with stage=`proposing` instead of creating a Proposal record.
3. **Fast-track evaluation**: Set `fast_track_eligible` per the rules in data-model.md.
4. **link_only override**: If `is_new_page=True`, force `link_only=False` (a new
   page cannot be link-only).

## Retry Policy

| Condition | Action |
|-----------|--------|
| Malformed JSON (parse error) | Retry once with stricter prompt suffix: "Respond with valid JSON only. No explanation, no markdown fences." |
| Second consecutive parse error | Send note to errors table, stage=`proposing` |
| Ollama timeout (> 60s) | Send note to errors table, stage=`proposing` |
| `confidence < 0.5` after post-processing | Send note to errors table, stage=`proposing` |

## Example Valid Response

```json
{
  "summary": "Esta nota explora como sistemas frágeis falham sob pressão enquanto sistemas antifrágeis se beneficiam da volatilidade. Taleb usa o exemplo da hidra como metáfora central.",
  "proposed_page": "antifragility",
  "is_new_page": false,
  "link_only": false,
  "proposed_links": ["via-negativa", "black-swan"],
  "confidence": 0.88,
  "flag_contradiction": false,
  "flag_duplicate": false
}
```

## Proposal Prompt Template

```python
PROPOSAL_PROMPT = """
You are maintaining a Zettelkasten wiki. Propose how a new note should be
integrated — do not invent connections that aren't clearly present.

Existing concepts in this domain (index):
{domain_index}

New note:
Title: {title}
Body: {body}
Language: {language}

Rules:
- Only propose [[wikilinks]] to concepts explicitly listed in the index above.
- If no link is warranted, return an empty proposed_links list.
- Do not hallucinate connections.
- Respond with valid JSON only, no preamble, no markdown fences.

JSON schema:
{{
  "summary": "string (2-3 sentences, same language as note)",
  "proposed_page": "string (slug: lowercase-hyphenated)",
  "is_new_page": bool,
  "link_only": bool,
  "proposed_links": ["slug1", "slug2"],
  "confidence": float,
  "flag_contradiction": bool,
  "flag_duplicate": bool
}}
"""
```
