"""
Job matching tool.
- Warms up the TF-IDF embedding engine on the full corpus before scoring.
- Returns semantic match score per job, matched/missing skills, and tier.
"""
from __future__ import annotations

from core.vector_store import (
    compute_match_score,
    upsert_jobs,
    _job_to_doc,
    _get_tfidf_engine,
    embed,
    _stable_id,
)
from core.config import get_logger

log = get_logger(__name__)


def match_jobs(
    resume_data: dict,
    jobs: list[dict],
    top_n: int = 10,
) -> list[dict]:
    """
    Match a resume against a list of jobs.

    Warmup: feeds the full corpus (resume + all job docs) into the embedding
    engine before scoring, so TF-IDF has proper IDF statistics.

    Returns ranked list with match_score, matched_skills, missing_skills, match_tier.
    """
    if not jobs:
        log.warning("No jobs provided to match against")
        return []

    resume_doc  = resume_data.get("resume_doc", "")
    resume_skills = {s.lower() for s in resume_data.get("skills", [])}

    # Build job docs
    job_docs = [_job_to_doc(j) for j in jobs]

    # Warm up embedding engine with combined corpus BEFORE scoring
    corpus = [resume_doc] + job_docs
    try:
        engine = _get_tfidf_engine()
        engine._ensure_fitted(corpus)
    except Exception:
        pass  # if sentence-transformers is active, this is a no-op

    # Store jobs in ChromaDB
    upsert_jobs(jobs)

    enriched = []
    for job, job_doc in zip(jobs, job_docs):
        score = compute_match_score(resume_doc, job_doc)

        job_skills  = {s.lower() for s in job.get("required_skills", [])}
        matched     = sorted(resume_skills & job_skills)
        missing     = sorted(job_skills - resume_skills)

        # Calibrate tiers for TF-IDF range (lower than MiniLM cosine scores)
        tier = (
            "strong"  if score >= 0.20
            else "good" if score >= 0.08
            else "stretch"
        )

        enriched.append({
            **job,
            "match_score": score,
            "matched_skills": matched,
            "missing_skills": missing,
            "match_tier": tier,
        })

    enriched.sort(key=lambda x: x["match_score"], reverse=True)
    log.info(
        "Matched %d jobs; top score=%.4f tier=%s",
        len(enriched),
        enriched[0]["match_score"] if enriched else 0,
        enriched[0]["match_tier"] if enriched else "-",
    )
    return enriched[:top_n]


def compute_aggregate_skill_gaps(
    resume_data: dict,
    matched_jobs: list[dict],
    top_n: int = 8,
) -> list[dict]:
    """
    Aggregate missing skills across all matched jobs.
    Returns ranked list of {skill, frequency, avg_job_score, priority}.
    """
    gap_counter: dict[str, list[float]] = {}
    for job in matched_jobs:
        for skill in job.get("missing_skills", []):
            gap_counter.setdefault(skill, []).append(job.get("match_score", 0))

    result = [
        {
            "skill":         skill,
            "frequency":     len(scores),
            "avg_job_score": round(sum(scores) / len(scores), 4),
            "priority":      round(len(scores) * (sum(scores) / len(scores)), 4),
        }
        for skill, scores in gap_counter.items()
    ]
    result.sort(key=lambda x: x["frequency"], reverse=True)  # freq more reliable than tiny score
    return result[:top_n]
