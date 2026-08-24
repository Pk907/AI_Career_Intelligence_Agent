"""
Job matching tool — Hybrid scoring (audit fix 2026-08-08).

Score formula (deterministic, explainable):
    hybrid_score = 0.55 × skill_overlap_ratio + 0.45 × cosine_similarity

skill_overlap_ratio = |matched_skills| / max(|job_skills|, 1)
  - This is the primary driver — how many of the job's required skills
    does the candidate have?

cosine_similarity = TF-IDF cosine between resume doc and job doc
  - Secondary signal — catches domain/keyword relevance not in skill lists.

Both skill sets are normalised to canonical names before comparison,
so "Hugging Face" == "huggingface" == "HF", "PyTorch" == "pytorch" etc.

Match tiers (calibrated for hybrid range):
    strong  : score >= 0.55
    good    : score >= 0.35
    stretch : score <  0.35
"""
from __future__ import annotations

import re
from collections import Counter
from core.vector_store import compute_match_score, upsert_jobs, _job_to_doc, _get_tfidf_engine
from core.config import get_logger

log = get_logger(__name__)

# ── Canonical alias map (mirrors resume_parser — keep in sync) ────────────────
_CANON: dict[str, str] = {
    "python": "Python", "py": "Python",
    "java": "Java", "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "c++": "C++", "cpp": "C++", "c#": "C#",
    "go": "Go", "golang": "Go", "rust": "Rust",
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "natural language processing": "NLP", "nlp": "NLP",
    "llm": "LLM", "large language model": "LLM",
    "generative ai": "Generative AI", "gen ai": "Generative AI",
    "rag": "RAG", "retrieval augmented generation": "RAG",
    "mlops": "MLOps",
    "data science": "Data Science",
    "pytorch": "PyTorch", "torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "keras": "Keras",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face", "hf": "Hugging Face",
    "transformers": "Transformers",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "openai": "OpenAI", "anthropic": "Anthropic",
    "pandas": "Pandas", "numpy": "NumPy", "scipy": "SciPy",
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "react": "React", "reactjs": "React",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "streamlit": "Streamlit",
    "sql": "SQL", "mysql": "MySQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis", "elasticsearch": "Elasticsearch",
    "chromadb": "ChromaDB", "pinecone": "Pinecone",
    "vector database": "Vector DB", "vector db": "Vector DB",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "terraform": "Terraform", "airflow": "Airflow",
    "spark": "Spark", "kafka": "Kafka",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
    "git": "Git", "linux": "Linux",
    "rest": "REST API", "rest api": "REST API", "restful": "REST API",
    "graphql": "GraphQL",
    "html": "HTML", "css": "CSS",
    "agile": "Agile", "scrum": "Scrum",
}


def _canonicalize(skill: str) -> str:
    """Return canonical skill name, normalised to a consistent form."""
    low = skill.strip().lower()
    return _CANON.get(low, skill.strip())


def _normalize_skill_set(skills: list[str]) -> set[str]:
    """Return a set of canonical skill names from a raw list."""
    return {_canonicalize(s) for s in skills if s.strip()}


def match_jobs(
    resume_data: dict,
    jobs: list[dict],
    top_n: int = 10,
) -> list[dict]:
    """
    Match resume against jobs using hybrid score.

    Parameters
    ----------
    resume_data : Parsed resume dict (must have 'skills' and 'resume_doc').
    jobs        : List of job dicts (from search_jobs).
    top_n       : Maximum results to return.

    Returns sorted list of job dicts enriched with:
        match_score, matched_skills, missing_skills, match_tier, score_breakdown
    """
    # Filter out sentinel entries
    real_jobs = [j for j in jobs if "__status__" not in j]
    if not real_jobs:
        log.warning("No real jobs to match against (all sentinels)")
        return []

    resume_doc    = resume_data.get("resume_doc", "")
    resume_skills = _normalize_skill_set(resume_data.get("skills", []))

    log.info(
        "match_jobs — %d jobs, resume has %d skills",
        len(real_jobs), len(resume_skills),
    )

    # Warm up TF-IDF on full corpus before scoring
    job_docs = [_job_to_doc(j) for j in real_jobs]
    corpus   = [resume_doc] + job_docs
    try:
        engine = _get_tfidf_engine()
        engine._ensure_fitted(corpus)
    except Exception:
        pass

    # Store jobs in ChromaDB
    upsert_jobs(real_jobs)

    enriched: list[dict] = []
    for job, job_doc in zip(real_jobs, job_docs):
        job_skills = _normalize_skill_set(job.get("required_skills", []))

        # Skill overlap component
        matched  = sorted(resume_skills & job_skills)
        missing  = sorted(job_skills - resume_skills)
        overlap  = len(matched) / max(len(job_skills), 1)

        # Cosine similarity component
        try:
            cosine = compute_match_score(resume_doc, job_doc)
        except Exception:
            cosine = 0.0

        # Hybrid score
        hybrid = round(0.55 * overlap + 0.45 * cosine, 4)
        hybrid = min(1.0, max(0.0, hybrid))

        # Tier calibration
        if hybrid >= 0.55:
            tier = "strong"
        elif hybrid >= 0.35:
            tier = "good"
        else:
            tier = "stretch"

        enriched.append({
            **job,
            "match_score":    hybrid,
            "matched_skills": matched,
            "missing_skills": missing,
            "match_tier":     tier,
            "score_breakdown": {
                "skill_overlap":  round(overlap, 4),
                "cosine_sim":     round(cosine, 4),
                "formula":        "0.55×overlap + 0.45×cosine",
            },
        })

    enriched.sort(key=lambda x: x["match_score"], reverse=True)
    top = enriched[:top_n]

    if top:
        log.info(
            "Matched %d jobs — top: %r score=%.2f tier=%s (overlap=%.2f, cosine=%.2f)",
            len(top), top[0].get("title", ""), top[0]["match_score"],
            top[0]["match_tier"],
            top[0]["score_breakdown"]["skill_overlap"],
            top[0]["score_breakdown"]["cosine_sim"],
        )

    return top


def compute_aggregate_skill_gaps(
    resume_data: dict,
    matched_jobs: list[dict],
    top_n: int = 8,
) -> list[dict]:
    """
    Aggregate missing skills across matched jobs.
    Returns ranked list: [{skill, frequency, avg_job_score, priority}]
    """
    gap_counter: dict[str, list[float]] = {}
    for job in matched_jobs:
        for skill in job.get("missing_skills", []):
            canon = _canonicalize(skill)
            gap_counter.setdefault(canon, []).append(job.get("match_score", 0))

    result = [
        {
            "skill":         skill,
            "frequency":     len(scores),
            "avg_job_score": round(sum(scores) / len(scores), 4),
            "priority":      round(len(scores) * (sum(scores) / len(scores)), 4),
        }
        for skill, scores in gap_counter.items()
    ]
    result.sort(key=lambda x: x["frequency"], reverse=True)
    return result[:top_n]
