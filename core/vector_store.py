"""
Embedding generation + ChromaDB persistence.

Embedding backend:
  Local TF-IDF + TruncatedSVD (instant startup, zero network deps).
  sentence-transformers is intentionally disabled to avoid the 60-90s
  cold-start delay that made the Analyze button appear frozen.

Both backends produce L2-normalised 384-dim dense vectors and expose
the same embed(texts) -> list[list[float]] interface.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from typing import Any

import chromadb

from core.config import (
    CHROMA_DIR,
    CHROMA_COLLECTION_RESUMES,
    CHROMA_COLLECTION_JOBS,
    EMBEDDING_MODEL,
    get_logger,
)

log = get_logger(__name__)

EMBED_DIM = 384          # target dimensionality
_encoder = None          # reserved for future sentence-transformers re-enable
_tfidf_engine = None     # TF-IDF fallback engine (lazy)


# ─────────────────────────────────────────────────────────────────────────────
# Embedding backends
# ─────────────────────────────────────────────────────────────────────────────

class _TFIDFEngine:
    """
    Lightweight local embedding: TF-IDF → TruncatedSVD → L2-normalise.
    Trained incrementally on every batch of texts it sees.
    """
    def __init__(self, n_components: int = EMBED_DIM):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        import numpy as np

        self.np = np
        self.n_components = n_components
        self._fitted = False
        self._corpus: list[str] = []

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_features=8000,
            sublinear_tf=True,
        )
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)

    def _ensure_fitted(self, texts: list[str]) -> None:
        """Add new texts to corpus and refit if needed."""
        new = [t for t in texts if t not in self._corpus]
        if new or not self._fitted:
            self._corpus.extend(new)
            corpus = self._corpus or texts
            tfidf = self.vectorizer.fit_transform(corpus)
            n_comp = min(self.n_components, tfidf.shape[1] - 1, tfidf.shape[0] - 1)
            if n_comp < 1:
                n_comp = 1
            self.svd.n_components = n_comp
            self.svd.fit(tfidf)
            self._fitted = True

    def encode(self, texts: list[str]) -> list[list[float]]:
        self._ensure_fitted(texts)
        tfidf = self.vectorizer.transform(texts)
        reduced = self.svd.transform(tfidf)  # (n, n_components)

        # Pad to EMBED_DIM if SVD produced fewer components
        if reduced.shape[1] < EMBED_DIM:
            pad = self.np.zeros((reduced.shape[0], EMBED_DIM - reduced.shape[1]))
            reduced = self.np.hstack([reduced, pad])

        # L2 normalise
        norms = self.np.linalg.norm(reduced, axis=1, keepdims=True)
        norms = self.np.where(norms == 0, 1, norms)
        normalised = reduced / norms
        return normalised.tolist()


def _get_tfidf_engine() -> _TFIDFEngine:
    global _tfidf_engine
    if _tfidf_engine is None:
        log.info("Initialising TF-IDF+SVD local embedding engine (dim=%d)", EMBED_DIM)
        _tfidf_engine = _TFIDFEngine(n_components=EMBED_DIM)
    return _tfidf_engine


# sentence-transformers is disabled to avoid 60-90s cold-start freeze.
# Set _st_unavailable = False here to re-enable it.
_st_unavailable = True


def _try_sentence_transformers(texts: list[str]) -> list[list[float]] | None:
    """Disabled — always returns None to use fast TF-IDF+SVD (instant startup)."""
    return None


def get_embedding_backend() -> str:
    """
    Return which embedding backend is currently active.
    """
    return "tfidf-svd-local"


def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings → L2-normalised dense vectors.
    Uses TF-IDF+SVD (instant, local, no network required).
    """
    if not texts:
        return []
    return _get_tfidf_engine().encode(texts)


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB client
# ─────────────────────────────────────────────────────────────────────────────

_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        log.info("Opening ChromaDB at %s", CHROMA_DIR)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def _collection(name: str):
    return get_chroma_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resume operations
# ─────────────────────────────────────────────────────────────────────────────

def _resume_to_doc(parsed: dict) -> str:
    parts = [
        "SUMMARY: "         + parsed.get("summary", ""),
        "SKILLS: "          + ", ".join(parsed.get("skills", [])),
        "EXPERIENCE: "      + parsed.get("experience", "")[:2000],
        "PROJECTS: "        + "; ".join(parsed.get("projects", [])),
        "CERTIFICATIONS: "  + "; ".join(parsed.get("certifications", [])),
        "EDUCATION: "       + parsed.get("education", ""),
    ]
    return "\n".join(p for p in parts if len(p) > 10)


def upsert_resume(parsed: dict) -> str:
    col = _collection(CHROMA_COLLECTION_RESUMES)
    doc_text = _resume_to_doc(parsed)
    doc_id   = _stable_id(doc_text)
    vec      = embed([doc_text])[0]

    col.upsert(
        ids=[doc_id],
        embeddings=[vec],
        documents=[doc_text],
        metadatas=[{
            "skills":           json.dumps(parsed.get("skills", [])),
            "years_experience": parsed.get("years_experience", 0),
            "projects":         json.dumps(parsed.get("projects", [])),
            "certifications":   json.dumps(parsed.get("certifications", [])),
        }],
    )
    log.info("Resume upserted → id=%s", doc_id)
    return doc_id


# ─────────────────────────────────────────────────────────────────────────────
# Job operations
# ─────────────────────────────────────────────────────────────────────────────

def _job_to_doc(job: dict) -> str:
    return "\n".join([
        f"TITLE: {job.get('title', '')}",
        f"COMPANY: {job.get('company', '')}",
        f"DESCRIPTION: {job.get('description', '')[:3000]}",
        f"REQUIRED SKILLS: {', '.join(job.get('required_skills', []))}",
    ])


def upsert_jobs(jobs: list[dict]) -> int:
    if not jobs:
        return 0
    col   = _collection(CHROMA_COLLECTION_JOBS)
    texts = [_job_to_doc(j) for j in jobs]
    ids   = [_stable_id(t) for t in texts]
    vecs  = embed(texts)
    metas = [
        {
            "title":    j.get("title", ""),
            "company":  j.get("company", ""),
            "location": j.get("location", ""),
            "url":      j.get("url", ""),
            "salary":   j.get("salary", ""),
            "source":   j.get("source", ""),
        }
        for j in jobs
    ]
    col.upsert(ids=ids, embeddings=vecs, documents=texts, metadatas=metas)
    log.info("Jobs upserted: %d", len(jobs))
    return len(jobs)


# ─────────────────────────────────────────────────────────────────────────────
# Similarity search
# ─────────────────────────────────────────────────────────────────────────────

def search_jobs_by_resume(resume_doc: str, n: int = 10) -> list[dict]:
    col = _collection(CHROMA_COLLECTION_JOBS)
    if col.count() == 0:
        log.warning("Job collection is empty – run job search first")
        return []
    vec     = embed([resume_doc])[0]
    results = col.query(
        query_embeddings=[vec],
        n_results=min(n, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({"meta": meta, "score": round(1 - dist, 4), "document": doc})
    return output


def compute_match_score(resume_text: str, job_description: str) -> float:
    """Cosine similarity between resume and job description embeddings."""
    vecs  = embed([resume_text, job_description])
    score = sum(a * b for a, b in zip(vecs[0], vecs[1]))
    return round(max(0.0, min(1.0, score)), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _stable_id(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def clear_jobs() -> None:
    get_chroma_client().delete_collection(CHROMA_COLLECTION_JOBS)
    log.info("Job collection cleared")
