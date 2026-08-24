"""
Job search tool — Production-ready, honest implementation.

Primary:  JSearch API via RapidAPI (RAPIDAPI_KEY from .env)
Fallback: LinkedIn deep-link search URLs — only used when key is present
          but returns empty results for a niche query.

When RAPIDAPI_KEY is missing:
  → Returns empty list + sets a flag so the UI shows
    "Live job search unavailable — add RAPIDAPI_KEY to .env"

When key is present but API fails (500 / timeout):
  → Returns empty list; UI shows same unavailable message.
  → Does NOT show fake "Multiple Companies" templates.

Key improvements (audit 2026-08-08):
  1. Explicit error type detection: auth/quota errors stop immediately.
  2. Deduplication by job_id before returning.
  3. Richer query: role + top candidate skills for better relevance.
  4. Alias normalization on extracted job skills.
  5. Honest no-results path — no fake company names.
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Always load .env from project root regardless of CWD (Streamlit changes CWD)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)

from core.config import get_logger

log = get_logger(__name__)

RAPIDAPI_HOST   = "jsearch.p.rapidapi.com"
REQUEST_TIMEOUT = 10   # per-page timeout (seconds)

# Alias map for job skill normalization (same as resume_parser canonical names)
_JOB_SKILL_ALIASES: dict[str, str] = {
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
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face",
    "transformers": "Transformers",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "openai": "OpenAI",
    "pandas": "Pandas", "numpy": "NumPy",
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
}

# Sentinel returned alongside empty list to tell UI WHY there are no jobs
NO_KEY_SENTINEL   = "__NO_RAPIDAPI_KEY__"
API_ERROR_SENTINEL = "__API_ERROR__"


def search_jobs(
    query: str,
    location: str = "Remote",
    candidate_skills: list[str] | None = None,
    num_pages: int = 2,
) -> list[dict]:
    """
    Search for real jobs.

    Returns list of job dicts. Each dict has a '__status__' key only on
    failure:  {'__status__': NO_KEY_SENTINEL} or {'__status__': API_ERROR_SENTINEL}
    Callers should check: if jobs and '__status__' in jobs[0]: handle_error()

    Parameters
    ----------
    query            : Target role string from user input
    location         : Location string from user input
    candidate_skills : Top skills from the parsed resume (improves relevance)
    num_pages        : JSearch pages to fetch (each page ≈ 10 jobs)
    """
    key = os.getenv("RAPIDAPI_KEY", "").strip()

    log.info(
        "search_jobs — query=%r location=%r key_set=%s skills=%s",
        query, location, bool(key), (candidate_skills or [])[:5],
    )

    if not key:
        log.warning("RAPIDAPI_KEY not set — live job search unavailable")
        return [{"__status__": NO_KEY_SENTINEL}]

    # Build a richer query: role + top 3 candidate skills for better relevance
    enriched_query = _build_query(query, candidate_skills)
    log.info("Enriched query: %r", enriched_query)

    jobs, error = _jsearch(enriched_query, location, num_pages, key)

    if error:
        log.warning("JSearch failed (%s) — returning error sentinel", error)
        return [{"__status__": API_ERROR_SENTINEL, "__error__": error}]

    if not jobs:
        # Key is valid but returned nothing — try broader query without skills
        log.info("No results for enriched query, retrying with base query only")
        jobs, error2 = _jsearch(query, location, num_pages, key)
        if error2 or not jobs:
            return [{"__status__": API_ERROR_SENTINEL, "__error__": error2 or "empty"}]

    # Deduplicate by job_id
    jobs = _deduplicate(jobs)
    log.info("search_jobs complete: %d unique jobs", len(jobs))
    return jobs


def _build_query(role: str, skills: list[str] | None) -> str:
    """Combine role + top 3 skills into a focused search query."""
    if not skills:
        return role
    top = skills[:3]
    skill_str = " ".join(top)
    return f"{role} {skill_str}".strip()


def _jsearch(
    query: str,
    location: str,
    num_pages: int,
    key: str,
) -> tuple[list[dict], str | None]:
    """
    Call JSearch API.
    Returns (jobs, error_string_or_None).
    Detects auth/quota errors and stops immediately instead of retrying.
    """
    headers = {
        "X-RapidAPI-Key":  key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    jobs: list[dict] = []

    for page in range(1, num_pages + 1):
        params: dict[str, Any] = {
            "query":     f"{query} {location}",
            "page":      page,
            "num_pages": 1,
            "date_posted": "month",          # past month — broad enough to get results
        }
        try:
            resp = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            # Detect auth/quota errors immediately — no point retrying
            if resp.status_code in (401, 403):
                msg = f"Auth error {resp.status_code}"
                log.error("JSearch auth error: %s", resp.text[:200])
                return [], msg
            if resp.status_code == 429:
                msg = "Rate limit / quota exceeded"
                log.error("JSearch rate limit: %s", resp.text[:200])
                return [], msg
            if resp.status_code == 500:
                # Server error — try without date_posted
                log.warning("JSearch 500 on page %d, retrying without date_posted", page)
                params.pop("date_posted", None)
                resp2 = requests.get(
                    "https://jsearch.p.rapidapi.com/search",
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp2.status_code != 200:
                    log.error("JSearch 500 retry also failed: %d", resp2.status_code)
                    return [], f"Server error {resp2.status_code}"
                resp = resp2

            resp.raise_for_status()
            data = resp.json().get("data", [])
            log.info("JSearch page %d: %d results", page, len(data))

            for item in data:
                job = _normalise_jsearch(item, query)
                if job:
                    jobs.append(job)

            time.sleep(0.3)

        except requests.Timeout:
            log.error("JSearch page %d timed out after %ds", page, REQUEST_TIMEOUT)
            # On timeout, return what we have (could be nothing)
            if jobs:
                break
            return [], f"Request timed out after {REQUEST_TIMEOUT}s"
        except Exception as exc:
            log.error("JSearch page %d error: %s", page, exc)
            return [], str(exc)

    return jobs, None


def _normalise_jsearch(item: dict, query: str) -> dict | None:
    """Normalise a raw JSearch API result into our standard job dict."""
    title   = (item.get("job_title") or "").strip()
    company = (item.get("employer_name") or "").strip()

    # Skip results with no title or company
    if not title or not company:
        return None

    desc = item.get("job_description") or ""
    job_id = item.get("job_id") or _stable_id(title + company)

    apply_url    = _best_apply_url(
        direct  = item.get("job_apply_link") or "",
        google  = item.get("job_google_link") or "",
        title   = title,
        company = company,
        query   = query,
    )
    linkedin_url = _linkedin_search_url(title, company)

    return {
        "job_id":          job_id,
        "title":           title,
        "company":         company,
        "location":        (item.get("job_city") or item.get("job_country") or "").strip(),
        "description":     desc[:4000],
        "required_skills": _extract_and_normalise_skills(desc),
        "url":             apply_url,
        "linkedin_url":    linkedin_url,
        "salary":          _format_salary(item),
        "source":          "JSearch (RapidAPI)",
        "posted_at":       item.get("job_posted_at_datetime_utc") or "",
        "employment_type": item.get("job_employment_type") or "",
        "is_remote":       bool(item.get("job_is_remote", False)),
        "employer_logo":   item.get("employer_logo") or "",
    }


def _extract_and_normalise_skills(desc: str) -> list[str]:
    """Extract skills from job description and normalise to canonical names."""
    lower = desc.lower()
    found: set[str] = set()
    for alias, canonical in _JOB_SKILL_ALIASES.items():
        if len(alias) <= 3:
            if re.search(r"\b" + re.escape(alias) + r"\b", lower):
                found.add(canonical)
        else:
            if alias in lower:
                found.add(canonical)
    return sorted(found)


def _deduplicate(jobs: list[dict]) -> list[dict]:
    """Remove duplicate jobs by job_id, keeping first occurrence."""
    seen: set[str] = set()
    out: list[dict] = []
    for job in jobs:
        jid = job.get("job_id", "")
        if jid and jid in seen:
            continue
        seen.add(jid)
        out.append(job)
    return out


# ── URL helpers ───────────────────────────────────────────────────────────────

def _is_valid_apply_url(url: str) -> bool:
    """Return True if url is a real direct apply link (not a search / placeholder)."""
    if not url or not url.startswith("http"):
        return False
    bad = ["example.com", "placeholder", "localhost", "127.0.0.1",
           "jsearch.p.rapidapi", "google.com/search?q="]
    lower = url.lower()
    return not any(p in lower for p in bad)


def _best_apply_url(direct: str, google: str, title: str, company: str, query: str) -> str:
    """Pick best apply URL: direct ATS > Google job page > LinkedIn search."""
    if _is_valid_apply_url(direct) and "google.com" not in direct.lower():
        return direct
    if _is_valid_apply_url(google) and "google.com/search" not in google.lower():
        return google
    return _linkedin_search_url(title or query, company)


def _linkedin_search_url(title: str, company: str = "") -> str:
    q = f"{title} {company}".strip() if company else title
    params = urllib.parse.urlencode({
        "keywords": q,
        "f_TPR":    "r2592000",   # past 30 days
        "position": 1,
        "pageNum":  0,
    })
    return f"https://www.linkedin.com/jobs/search/?{params}"


def _format_salary(item: dict) -> str:
    lo     = item.get("job_min_salary")
    hi     = item.get("job_max_salary")
    period = item.get("job_salary_period") or ""
    if lo and hi:
        return f"${lo:,.0f} – ${hi:,.0f} / {period}"
    if lo:
        return f"${lo:,.0f}+ / {period}"
    return ""


def _stable_id(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]
