"""
Job search tool.
Primary:  JSearch API via RapidAPI (if RAPIDAPI_KEY is set)
Fallback: Scrapes RemoteOK and HN Who's Hiring patterns for demo data
"""
from __future__ import annotations

import time
import re
import requests
from typing import Any

import os
from core.config import get_logger

log = get_logger(__name__)

RAPIDAPI_HOST = "jsearch.p.rapidapi.com"
REQUEST_TIMEOUT = 10


def search_jobs(
    query: str,
    location: str = "Remote",
    num_pages: int = 2,
) -> list[dict]:
    """
    Return a list of job dicts with: title, company, location,
    description, required_skills, url, salary, source.
    """
    log.info(
        "SEARCH_JOBS CALLED — query=%r location=%r rapidapi_key_set=%s",
        query, location, bool(os.getenv("RAPIDAPI_KEY", "")),
    )
    if os.getenv("RAPIDAPI_KEY", ""):
        jobs = _jsearch(query, location, num_pages)
        if jobs:
            return jobs
        log.warning("JSearch returned 0 results, falling back")

    return _fallback_jobs(query, location)


def _jsearch(query: str, location: str, num_pages: int) -> list[dict]:
    """Call the JSearch RapidAPI endpoint."""
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", ""),
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    jobs: list[dict] = []
    for page in range(1, num_pages + 1):
        try:
            resp = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers=headers,
                params={"query": f"{query} {location}", "page": page, "num_pages": 1},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for item in data:
                jobs.append(_normalise_jsearch(item))
            time.sleep(0.5)
        except Exception as exc:
            log.error("JSearch page %d failed: %s", page, exc)
    return jobs


def _normalise_jsearch(item: dict) -> dict:
    desc = item.get("job_description", "")
    return {
        "title": item.get("job_title", ""),
        "company": item.get("employer_name", ""),
        "location": item.get("job_city", "") or item.get("job_country", ""),
        "description": desc[:3000],
        "required_skills": _extract_skills_from_desc(desc),
        "url": item.get("job_apply_link", item.get("job_google_link", "")),
        "salary": _format_salary(item),
        "source": "JSearch",
        "posted_at": item.get("job_posted_at_datetime_utc", ""),
        "employment_type": item.get("job_employment_type", ""),
        "is_remote": item.get("job_is_remote", False),
    }


def _format_salary(item: dict) -> str:
    lo = item.get("job_min_salary")
    hi = item.get("job_max_salary")
    period = item.get("job_salary_period", "")
    if lo and hi:
        return f"${lo:,.0f} – ${hi:,.0f} / {period}"
    return ""


def _extract_skills_from_desc(desc: str) -> list[str]:
    """Quick regex skill extraction from job description."""
    skill_tokens = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++",
        "react", "node", "fastapi", "flask", "django", "aws", "gcp", "azure",
        "docker", "kubernetes", "sql", "mongodb", "postgresql", "redis",
        "tensorflow", "pytorch", "scikit-learn", "llm", "nlp", "machine learning",
        "deep learning", "langchain", "hugging face", "mlops", "spark",
        "kafka", "airflow", "git", "linux", "rest api", "graphql",
    ]
    lower = desc.lower()
    return [tok for tok in skill_tokens if tok in lower]


# ── Fallback / demo data ─────────────────────────────────────────────────────

def _fallback_jobs(query: str, location: str) -> list[dict]:
    """
    Generate realistic demo jobs when no API key is set.
    Templates are filtered/ranked by relevance to `query`, and `location`
    is injected into every result so the UI reflects what the user asked for.

    NOTE: this is demo data only. Without RAPIDAPI_KEY, results are drawn
    from a fixed template pool — they will not include companies/roles
    outside that pool. Set RAPIDAPI_KEY in .env for live job search.
    """
    log.info("FALLBACK JOB SEARCH — query=%r location=%r (no RAPIDAPI_KEY set)", query, location)
    q_tokens = set(re.findall(r"[a-z0-9+#.]+", query.lower()))

    templates = [
        {
            "title": "AI/ML Engineer",
            "company": "Sarvam AI",
            "location": "Remote / Bangalore",
            "description": (
                "Build and deploy LLM-based products. Work with Python, PyTorch, "
                "Hugging Face, LangChain, FastAPI. Design RAG pipelines and fine-tune "
                "open-source models. Experience with vector databases preferred."
            ),
            "required_skills": ["python", "pytorch", "langchain", "hugging face", "fastapi", "docker"],
            "url": "https://jobs.sarvam.ai",
            "salary": "₹12L – ₹25L",
            "source": "Demo",
        },
        {
            "title": "Python Developer – AI Products",
            "company": "Krutrim AI",
            "location": "Remote",
            "description": (
                "Develop backend services for AI-powered applications. "
                "Python, FastAPI, Docker, AWS required. LLM integration a plus."
            ),
            "required_skills": ["python", "fastapi", "docker", "aws", "llm"],
            "url": "https://krutrim.ai/careers",
            "salary": "₹8L – ₹18L",
            "source": "Demo",
        },
        {
            "title": "Data Science Engineer",
            "company": "Bangalore Startup (via LinkedIn)",
            "location": "Bangalore / Remote",
            "description": (
                "Build ML pipelines, analyse large datasets, deploy models to production. "
                "Scikit-learn, pandas, SQL, cloud experience needed."
            ),
            "required_skills": ["python", "scikit-learn", "pandas", "sql", "docker"],
            "url": "https://linkedin.com/jobs",
            "salary": "₹7L – ₹15L",
            "source": "Demo",
        },
        {
            "title": "MLOps Engineer",
            "company": "Fractal Analytics",
            "location": "Mumbai / Remote",
            "description": (
                "Manage ML infrastructure, automate model deployment, build monitoring. "
                "Docker, Kubernetes, Airflow, MLflow required."
            ),
            "required_skills": ["python", "docker", "kubernetes", "airflow", "mlops"],
            "url": "https://fractal.ai/careers",
            "salary": "₹10L – ₹20L",
            "source": "Demo",
        },
        {
            "title": "Backend Engineer – Automation",
            "company": "Zoho",
            "location": "Chennai / Remote",
            "description": (
                "Build automation workflows, REST APIs, integrate third-party services. "
                "Python or Java, REST API, SQL, Git required."
            ),
            "required_skills": ["python", "rest api", "sql", "git", "docker"],
            "url": "https://careers.zoho.com",
            "salary": "₹6L – ₹12L",
            "source": "Demo",
        },
        {
            "title": "NLP Research Engineer",
            "company": "AI4Bharat",
            "location": "Remote",
            "description": (
                "Research and develop NLP models for Indic languages. "
                "PyTorch, Hugging Face Transformers, Python. Publications a plus."
            ),
            "required_skills": ["python", "pytorch", "nlp", "hugging face", "deep learning"],
            "url": "https://ai4bharat.org/jobs",
            "salary": "₹8L – ₹16L",
            "source": "Demo",
        },
        {
            "title": "Automation Test Engineer",
            "company": "Infosys BPM",
            "location": "Pune / Remote",
            "description": (
                "Automate testing workflows using Python, Selenium. "
                "Build CI/CD pipelines. REST API testing experience preferred."
            ),
            "required_skills": ["python", "git", "rest api", "linux"],
            "url": "https://infosys.com/careers",
            "salary": "₹4L – ₹8L",
            "source": "Demo",
        },
        {
            "title": "Full Stack Developer (Python + React)",
            "company": "HealthTech Startup",
            "location": "Remote",
            "description": (
                "Build web applications with Python Django/FastAPI backend and React frontend. "
                "PostgreSQL, Docker, AWS deployment."
            ),
            "required_skills": ["python", "react", "django", "postgresql", "docker", "aws"],
            "url": "https://wellfound.com/jobs",
            "salary": "₹8L – ₹18L",
            "source": "Demo",
        },
    ]

    # ── Rank templates by relevance to the user's query ──────────────────────
    def _relevance(job: dict) -> int:
        job_tokens = set(re.findall(r"[a-z0-9+#.]+", job["title"].lower())) | \
                     set(s.lower() for s in job.get("required_skills", []))
        return len(q_tokens & job_tokens)

    if q_tokens:
        templates.sort(key=_relevance, reverse=True)
        if _relevance(templates[0]) == 0:
            log.warning(
                "FALLBACK JOB SEARCH — no template matched query=%r; "
                "returning unranked demo pool. This is a known limitation of "
                "the static fallback pool. Add RAPIDAPI_KEY for real results.",
                query,
            )

    # ── Inject the user's requested location into every result ───────────────
    out = []
    for job in templates:
        job_copy = dict(job)
        if location:
            job_copy["location"] = f"{location} (demo data — template default: {job['location']})"
        out.append(job_copy)

    return out
