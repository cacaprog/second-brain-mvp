"""
Read-only MCP server for Second Brain v2.
Exposes the compiled wiki to Claude Code and other MCP-compatible agents.
All write operations are explicitly rejected.

Usage:
  python src/mcp_server.py [--port 8765] [--host localhost]
"""
import json
import sys
from pathlib import Path

import yaml
from fastmcp import FastMCP

from wiki_store import (
    list_all_pages,
    list_domain_slugs,
    read_wiki_page_by_slug,
)
from query import search_and_synthesize

mcp = FastMCP("second-brain")


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("wiki://{slug}")
def get_wiki_page(slug: str) -> str:
    """Return a single compiled wiki page by slug."""
    content = read_wiki_page_by_slug(slug)
    if content is None:
        raise ValueError(f"Page '{slug}' not found in wiki")
    return content


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def query_knowledge_base(question: str, domain: str | None = None) -> str:
    """
    Semantic search + Ollama synthesis over the compiled wiki.
    Optionally restrict to a single domain slug.
    """
    return search_and_synthesize(question, domain=domain)


@mcp.tool()
def list_domains() -> str:
    """List all domains in the wiki with their page counts."""
    pages = list_all_pages()
    domain_counts: dict[str, int] = {}
    for page in pages:
        d = page["domain"]
        domain_counts[d] = domain_counts.get(d, 0) + 1
    result = [{"domain": d, "page_count": c} for d, c in sorted(domain_counts.items())]
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def list_pages(domain: str) -> str:
    """List all compiled wiki pages in a given domain."""
    pages = list_all_pages()
    domain_pages = [
        {
            "slug": p["slug"],
            "updated": p.get("updated", ""),
            "confidence": p.get("confidence", 0.0),
        }
        for p in pages
        if p["domain"] == domain
    ]
    return json.dumps(domain_pages, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = _load_settings()
    port = cfg["mcp"]["port"]
    host = cfg["mcp"]["host"]

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]

    print(f"[MCP] Second Brain server starting on {host}:{port} (read-only)")
    mcp.run(port=port, host=host)
