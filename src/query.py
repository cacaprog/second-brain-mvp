"""
Query pipeline for Second Brain v2.
Retrieves relevant wiki pages via ChromaDB (bi-encoder + optional cross-encoder re-ranking)
and synthesizes an answer using Ollama.

Usage:
  python src/query.py "question" [--domain DOMAIN]
"""
import sys
from pathlib import Path
from typing import Optional

import yaml


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


QUERY_PROMPT = """You are answering questions using a personal knowledge base (Zettelkasten).
Use only the wiki pages provided below. Cite sources using [[wikilink]] notation.
Do not add information not present in the pages below.
If the answer cannot be found, say so explicitly.

Wiki pages:
{retrieved_pages}

Question: {question}
/no_think"""

NOT_FOUND_MSG = "The answer to this question was not found in the knowledge base."


def _call_ollama(model: str, prompt: str, timeout: int) -> str:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    import ollama

    def _call():
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            think=False,
        )
        return response["message"]["content"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        return future.result(timeout=timeout)


def search_and_synthesize(question: str, domain: Optional[str] = None, n_results: int = 5) -> str:
    """
    Full query pipeline:
    1. Retrieve wiki pages (single-domain or cross-domain with re-ranking)
    2. Synthesize an answer using Ollama
    Returns the answer string with [[wikilink]] citations.
    """
    from vector_store import get_vector_store

    cfg = _load_settings()
    model = cfg["ollama"]["model"]
    timeout = cfg["ollama"]["timeout_seconds"]

    store = get_vector_store()

    if domain:
        results = store.search(question, domain=domain, n_results=n_results)
    else:
        results = store.cross_domain_search(question, n_results=n_results)

    if not results:
        return NOT_FOUND_MSG

    pages_text = "\n\n---\n\n".join(
        f"[{r['metadata'].get('slug', '?')}]\n{r['content'][:2000]}"
        for r in results
    )

    prompt = QUERY_PROMPT.format(retrieved_pages=pages_text, question=question)

    try:
        answer = _call_ollama(model, prompt, timeout)
    except Exception as e:
        return f"[Query error: {e}]"

    # Append source list
    source_slugs = [r["metadata"].get("slug", "?") for r in results]
    sources_line = "Sources: " + ", ".join(f"[[{s}]]" for s in source_slugs)
    return answer.strip() + f"\n\n{sources_line}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/query.py 'question' [--domain DOMAIN]")
        sys.exit(1)

    question = sys.argv[1]
    domain_arg = None
    if "--domain" in sys.argv:
        idx = sys.argv.index("--domain")
        if idx + 1 < len(sys.argv):
            domain_arg = sys.argv[idx + 1]

    answer = search_and_synthesize(question, domain=domain_arg)
    print(answer)
