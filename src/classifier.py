"""
Two-stage domain classifier for Second Brain v2.
Stage 1: keyword scoring against domains.yaml seed terms (fast, zero-cost).
Stage 2: cosine similarity against pre-computed domain centroid embeddings
         (used only when top-2 keyword scores are within 0.10).
"""
import pickle
import sys
from pathlib import Path
from typing import Optional

import yaml

# Module-level caches — loaded once per process, never re-read.
_settings_cache: Optional[dict] = None
_domains_cache: Optional[dict] = None
_centroids_cache: Optional[dict] = None
_encoder_cache = None  # SentenceTransformer instance


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is None:
        cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        with open(cfg_path) as f:
            _settings_cache = yaml.safe_load(f)
    return _settings_cache


def _resolve_device(device: str) -> str:
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            return "cpu"
    return device


def _load_domains() -> dict:
    global _domains_cache
    if _domains_cache is None:
        cfg = _load_settings()
        domains_path = Path(__file__).parent.parent / cfg["domains"]["config_file"]
        with open(domains_path) as f:
            _domains_cache = yaml.safe_load(f)["domains"]
    return _domains_cache


def _centroids_path() -> Path:
    cfg = _load_settings()
    return Path(__file__).parent.parent / cfg["paths"]["centroids"]


def _keyword_score(text: str, seeds: list[str]) -> float:
    """Count how many seed terms appear in the text (case-insensitive)."""
    text_lower = text.lower()
    matches = sum(1 for seed in seeds if seed.lower() in text_lower)
    return matches / max(len(seeds), 1)


def keyword_classify(body: str, domains: dict | None = None) -> str:
    """
    Classify text using keyword scoring only (Stage 1) — no model load.
    Returns the domain name with the highest keyword score, or the first
    domain as fallback when all scores are zero.

    Accepts an optional pre-loaded domains dict to avoid repeated YAML reads
    when classifying many highlights in a loop.
    """
    d = domains if domains is not None else _load_domains()
    if not d:
        return "personal"
    scores = {
        name: _keyword_score(body, cfg.get("seeds", []))
        for name, cfg in d.items()
    }
    return max(scores, key=lambda k: scores[k])


def precompute_centroids() -> None:
    """
    Pre-compute domain centroid embeddings from seed terms and cache to
    config/centroids.pkl. Run once at setup or after domains.yaml changes.
    """
    import numpy as np

    cfg = _load_settings()
    domains = _load_domains()

    print("Loading embedding model for centroid computation...")
    encoder = _get_encoder()

    model_name = cfg["embeddings"]["model"]
    use_e5_prefix = "e5" in model_name.lower()

    centroids = {}
    for domain_name, domain_cfg in domains.items():
        seeds = domain_cfg.get("seeds", [])
        if not seeds:
            continue
        seed_texts = [f"passage: {s}" for s in seeds] if use_e5_prefix else seeds
        embeddings = encoder.encode(seed_texts, convert_to_numpy=True)
        centroids[domain_name] = embeddings.mean(axis=0)
        print(f"[OK] {domain_name} centroid computed ({len(seeds)} seeds)")

    _centroids_path().parent.mkdir(parents=True, exist_ok=True)
    with open(_centroids_path(), "wb") as f:
        pickle.dump(centroids, f)
    print(f"Centroids saved to {_centroids_path()}")


def _load_centroids() -> dict:
    global _centroids_cache
    if _centroids_cache is None:
        p = _centroids_path()
        if not p.exists():
            _centroids_cache = {}
        else:
            with open(p, "rb") as f:
                _centroids_cache = pickle.load(f)
    return _centroids_cache


def _get_encoder():
    global _encoder_cache
    if _encoder_cache is None:
        from sentence_transformers import SentenceTransformer
        cfg = _load_settings()
        _encoder_cache = SentenceTransformer(
            cfg["embeddings"]["model"],
            device=_resolve_device(cfg["embeddings"]["device"]),
        )
    return _encoder_cache


def classify(body: str) -> tuple[str, Optional[str]]:
    """
    Classify a note body into (primary_domain, secondary_domain | None).

    Returns the first domain in domains.yaml as fallback if no seeds match.
    Secondary domain is set when top-2 scores are within 0.05 after stage 2.
    """
    import numpy as np

    domains = _load_domains()
    if not domains:
        return "personal", None

    # Stage 1: keyword scoring
    scores: dict[str, float] = {}
    for domain_name, domain_cfg in domains.items():
        seeds = domain_cfg.get("seeds", [])
        scores[domain_name] = _keyword_score(body, seeds)

    sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_name, top_score = sorted_domains[0]
    second_name, second_score = sorted_domains[1] if len(sorted_domains) > 1 else (None, 0.0)

    # If top score is unambiguous, return immediately
    if top_score == 0.0:
        # No keyword match — fall through to centroid comparison
        pass
    elif second_name is None or (top_score - second_score) > 0.10:
        return top_name, None

    # Stage 2: centroid cosine similarity
    centroids = _load_centroids()
    if not centroids:
        # Centroids not computed yet — return best keyword match
        return top_name, None

    cfg = _load_settings()
    model_name = cfg["embeddings"]["model"]
    encoder = _get_encoder()
    text = f"passage: {body[:1000]}" if "e5" in model_name.lower() else body[:1000]
    note_emb = encoder.encode(text, convert_to_numpy=True)

    centroid_scores: dict[str, float] = {}
    for domain_name, centroid in centroids.items():
        sim = float(np.dot(note_emb, centroid) / (np.linalg.norm(note_emb) * np.linalg.norm(centroid) + 1e-9))
        centroid_scores[domain_name] = sim

    sorted_centroid = sorted(centroid_scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_centroid[0][0]
    secondary = None
    if len(sorted_centroid) > 1:
        if (sorted_centroid[0][1] - sorted_centroid[1][1]) <= 0.05:
            secondary = sorted_centroid[1][0]

    return primary, secondary


if __name__ == "__main__":
    if "--precompute" in sys.argv:
        precompute_centroids()
    else:
        print("Usage: python src/classifier.py --precompute")
