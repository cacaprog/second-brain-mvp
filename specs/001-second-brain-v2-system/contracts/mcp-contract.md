# MCP Server Contract

**Phase 1 output** | **Date**: 2026-04-21
**Server name**: `second-brain`
**Transport**: HTTP, localhost:8765 (default)
**Access**: Read-only — all write operations return an error

---

## Resources

### `wiki://{slug}`

Retrieve a single compiled wiki page by its slug.

**URI template**: `wiki://{slug}`

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slug` | string | yes | Lowercase-hyphenated page identifier |

**Response**: Full markdown content of the wiki page including YAML front matter.

**Errors**:
| Condition | Error message |
|-----------|---------------|
| Slug not found | `"Page '{slug}' not found in wiki"` |
| Wiki directory inaccessible | `"Wiki storage unavailable"` |

**Example**:
```
Resource: wiki://antifragility
Returns:
---
slug: antifragility
domain: philosophy
...
---

## Antifragility
...
```

---

## Tools

### `query_knowledge_base`

Semantic search over the compiled wiki with Ollama synthesis.

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `question` | string | yes | — | Natural language question in any supported language |
| `domain` | string | no | null | Restrict search to a single domain slug |

**Response**: Synthesized answer string with `[[wikilink]]` citations embedded.

**Behavior**:
- If `domain` is provided: single-domain bi-encoder retrieval, no re-ranking
- If `domain` is null: cross-domain bi-encoder + cross-encoder re-ranking
- If no relevant pages found: returns `"The answer to this question was not found in the knowledge base."`
- Answer language matches the question language (multilingual-e5-large is language-agnostic)

**Errors**:
| Condition | Error message |
|-----------|---------------|
| Ollama unavailable | `"LLM synthesis unavailable — Ollama not running"` |
| ChromaDB unavailable | `"Search index unavailable"` |

**Example**:
```json
{
  "question": "O que é antifragilidade e como se relaciona com via negativa?",
  "domain": "philosophy"
}
```
Response:
```
Antifragilidade é a propriedade de sistemas que se beneficiam de choques e 
volatilidade [[antifragility]]. A via negativa — conhecer pelo que evitar em 
vez do que buscar — é uma das práticas que Taleb associa à antifragilidade 
[[via-negativa]].
```

### `list_domains`

List all domains currently in the wiki with page counts.

**Parameters**: none

**Response**: JSON array of objects:
```json
[
  {"domain": "philosophy", "page_count": 42},
  {"domain": "analytics", "page_count": 78}
]
```

### `list_pages`

List all wiki pages in a domain.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `domain` | string | yes | Domain slug |

**Response**: JSON array of page summaries:
```json
[
  {"slug": "antifragility", "updated": "2026-04-21", "confidence": 0.82},
  {"slug": "via-negativa", "updated": "2026-03-15", "confidence": 0.91}
]
```

---

## Write Rejection Contract

Any operation that would modify the wiki, ChromaDB, or brain.sqlite MUST be rejected
with a structured error:

```json
{
  "error": "write operations are not permitted via the MCP interface",
  "code": "WRITE_FORBIDDEN"
}
```

This applies to any tool that is not listed above.

---

## Server Startup

```bash
python src/mcp_server.py [--port 8765] [--host localhost]
```

The server is stateless with respect to sessions — it reads from the wiki files and
ChromaDB on each request. No authentication is implemented (localhost-only binding
provides network isolation).
