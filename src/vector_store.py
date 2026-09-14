"""
Per-domain ChromaDB vector store with GPU-accelerated bi-encoder retrieval
and cross-encoder re-ranking for cross-domain search.
"""
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings


def _load_settings() -> dict:
    import yaml
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _resolve_device(device: str) -> str:
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            return "cpu"
    return device


class VectorStore:
    """
    Per-domain ChromaDB collections with bi-encoder retrieval and
    optional cross-encoder re-ranking for cross-domain queries.
    """

    def __init__(self, chroma_path: Optional[str] = None):
        cfg = _load_settings()
        path = chroma_path or cfg["paths"]["chroma"]
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._bi_encoder = None
        self._cross_encoder = None
        self._cfg = cfg

    def _get_bi_encoder(self):
        if self._bi_encoder is None:
            from sentence_transformers import SentenceTransformer
            self._bi_encoder = SentenceTransformer(
                self._cfg["embeddings"]["model"],
                device=_resolve_device(self._cfg["embeddings"]["device"]),
            )
        return self._bi_encoder

    def _get_cross_encoder(self):
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(
                self._cfg["reranker"]["model"],
                device=_resolve_device(self._cfg["reranker"]["device"]),
            )
        return self._cross_encoder

    def get_collection(self, domain: str):
        return self._client.get_or_create_collection(
            name=f"domain_{domain}",
            metadata={"hnsw:space": "cosine"},
        )

    def list_domains(self) -> list[str]:
        return [
            c.name.removeprefix("domain_")
            for c in self._client.list_collections()
            if c.name.startswith("domain_")
        ]

    def _encode(self, text: str) -> list[float]:
        """Encode text with the active bi-encoder. bge-m3 uses raw text; e5 uses prefixes."""
        encoder = self._get_bi_encoder()
        model_name = self._cfg["embeddings"]["model"]
        if "e5" in model_name.lower():
            # intfloat/multilingual-e5-* requires "query: " / "passage: " prefixes
            prefix = "passage: " if not text.startswith("query: ") else ""
            return encoder.encode(f"{prefix}{text}", convert_to_numpy=True).tolist()
        # bge-m3 and most other models: raw text
        return encoder.encode(text, convert_to_numpy=True).tolist()

    def _encode_query(self, query: str) -> list[float]:
        encoder = self._get_bi_encoder()
        model_name = self._cfg["embeddings"]["model"]
        if "e5" in model_name.lower():
            return encoder.encode(f"query: {query}", convert_to_numpy=True).tolist()
        return encoder.encode(query, convert_to_numpy=True).tolist()

    def upsert(self, slug: str, content: str, domain: str, language: str) -> None:
        """Idempotent upsert of a wiki page into its domain collection."""
        embedding = self._encode(content)
        from datetime import date
        self.get_collection(domain).upsert(
            ids=[slug],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"slug": slug, "domain": domain, "language": language, "updated": date.today().isoformat()}],
        )

    def delete_embedding(self, slug: str, domain: str) -> None:
        """Remove a slug's embedding from its domain collection. No-op if not found."""
        try:
            self.get_collection(domain).delete(ids=[slug])
        except Exception:
            pass

    def search(self, query: str, domain: str, n_results: int = 5) -> list[dict]:
        """Single-domain bi-encoder retrieval."""
        q_emb = self._encode_query(query)
        results = self.get_collection(domain).query(
            query_embeddings=[q_emb],
            n_results=min(n_results, self.get_collection(domain).count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(results)

    def cross_domain_search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Cross-domain search: bi-encoder retrieves top-10 per domain,
        then cross-encoder re-ranks all candidates.
        """
        q_emb = self._encode_query(query)

        candidates = []
        candidates_per_domain = self._cfg["reranker"]["cross_domain_candidates_per_domain"]
        for domain in self.list_domains():
            col = self.get_collection(domain)
            count = col.count()
            if count == 0:
                continue
            results = col.query(
                query_embeddings=[q_emb],
                n_results=min(candidates_per_domain, count),
                include=["documents", "metadatas", "distances"],
            )
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                candidates.append((doc, meta))

        if not candidates:
            return []

        cross_encoder = self._get_cross_encoder()
        pairs = [[query, doc] for doc, _ in candidates]
        scores = cross_encoder.predict(pairs)
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        return [
            {"content": doc, "metadata": meta, "score": float(score)}
            for score, (doc, meta) in ranked[:n_results]
        ]

    def query_similar(self, text: str, threshold: float = 0.90) -> Optional[str]:
        """
        Check if any existing wiki page is similar to the given text.
        Returns the slug of the closest page if similarity >= threshold, else None.
        Used for deduplication.
        """
        embedding = self._encode(text)

        best_slug = None
        best_sim = 0.0
        for domain in self.list_domains():
            col = self.get_collection(domain)
            if col.count() == 0:
                continue
            results = col.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["distances", "metadatas"],
            )
            if results["distances"][0]:
                sim = 1.0 - results["distances"][0][0]
                if sim > best_sim:
                    best_sim = sim
                    best_slug = results["metadatas"][0][0]["slug"]

        if best_sim >= threshold:
            return best_slug
        return None

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        out = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            out.append({"content": doc, "metadata": meta, "score": float(1.0 - dist)})
        return out


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
