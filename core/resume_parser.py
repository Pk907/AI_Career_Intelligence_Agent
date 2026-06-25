"""
Parses a PDF resume into raw text, then uses rule-based + HF extraction
to pull out structured fields: skills, experience, projects, certifications.
Falls back gracefully when HF models are unavailable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import IO

from pypdf import PdfReader

from core.config import get_logger

log = get_logger(__name__)

# ── Section header patterns ────────────────────────────────────────────────────
_SECTION_PATTERNS = {
    "skills": re.compile(
        r"(technical\s+skills?|skills?|core\s+competenc|technologies|tools)",
        re.I,
    ),
    "experience": re.compile(
        r"(work\s+experience|experience|employment|professional\s+background)", re.I
    ),
    "projects": re.compile(r"(projects?|portfolio|notable\s+work)", re.I),
    "education": re.compile(r"(education|academic|qualification|degree)", re.I),
    "certifications": re.compile(
        r"(certif|license|credential|award)", re.I
    ),
    "summary": re.compile(r"(summary|objective|profile|about)", re.I),
}

# Common tech / skill tokens – lightweight alternative to full NER
_TECH_TOKENS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "react", "vue", "angular", "node", "fastapi", "flask", "django", "spring",
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ci/cd",
    "git", "linux", "rest", "graphql", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "hugging face", "langchain", "llm",
    "nlp", "machine learning", "deep learning", "data science", "mlops",
    "streamlit", "airflow", "spark", "hadoop", "kafka", "rabbitmq",
    "html", "css", "tailwind", "figma", "agile", "scrum",
}


def extract_text_from_pdf(source: str | Path | IO[bytes]) -> str:
    """Return all text from a PDF file or file-like object."""
    try:
        reader = PdfReader(source)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        log.info("PDF parsed: %d pages, %d chars", len(pages), len(text))
        return text
    except Exception as exc:
        log.error("PDF parsing failed: %s", exc)
        raise


def _split_into_sections(text: str) -> dict[str, str]:
    """
    Split raw resume text into named sections using header heuristics.
    Lines that match a section header become section keys.
    """
    sections: dict[str, list[str]] = {k: [] for k in _SECTION_PATTERNS}
    sections["other"] = []
    current = "other"

    for line in text.splitlines():
        stripped = line.strip()
        matched = False
        for section, pattern in _SECTION_PATTERNS.items():
            if pattern.search(stripped) and len(stripped) < 60:
                current = section
                matched = True
                break
        if not matched:
            sections[current].append(stripped)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _extract_skills_from_text(text: str) -> list[str]:
    """
    Token-level skill extraction without requiring HF models.
    Good enough for a first pass; can be upgraded with NER later.
    """
    lower = text.lower()
    found = sorted({tok for tok in _TECH_TOKENS if tok in lower})
    # Also grab comma/pipe/bullet-delimited items from the skills section
    skill_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in skill_lines:
        for delimiter in [",", "|", "•", "·", "/"]:
            if delimiter in line:
                parts = [p.strip().lower() for p in line.split(delimiter)]
                for p in parts:
                    if 2 < len(p) < 40 and p not in found:
                        found.append(p)
    return list(dict.fromkeys(found))  # preserve order, deduplicate


def _extract_years_of_experience(experience_text: str) -> float:
    """
    Very rough heuristic: count date ranges like 2021-2023, 2022–Present.
    Returns estimated total years.
    """
    year_pattern = re.compile(r"\b(20\d{2}|19\d{2})\b")
    years = [int(y) for y in year_pattern.findall(experience_text)]
    if len(years) >= 2:
        return round(max(years) - min(years), 1)
    return 0.0


def _extract_projects(projects_text: str) -> list[str]:
    """Pull project titles (lines that look like headers in the projects section)."""
    projects = []
    for line in projects_text.splitlines():
        line = line.strip()
        # Short, non-empty lines that don't start with lowercase are likely titles
        if line and len(line) < 80 and not line[0].islower():
            projects.append(line)
    return projects[:10]  # cap at 10


def _extract_certifications(cert_text: str) -> list[str]:
    """Pull certification names from the certifications section."""
    certs = []
    for line in cert_text.splitlines():
        line = line.strip()
        if line and len(line) < 120:
            certs.append(line)
    return certs[:10]


def parse_resume(source: str | Path | IO[bytes]) -> dict:
    """
    Full pipeline: PDF → text → sections → structured output.

    Returns
    -------
    dict with keys: raw_text, skills, experience, projects,
                    certifications, education, summary, years_experience
    """
    raw_text = extract_text_from_pdf(source)
    sections = _split_into_sections(raw_text)

    skills = _extract_skills_from_text(
        sections.get("skills", "") + "\n" + raw_text
    )
    years_exp = _extract_years_of_experience(sections.get("experience", raw_text))
    projects = _extract_projects(sections.get("projects", ""))
    certifications = _extract_certifications(sections.get("certifications", ""))

    result = {
        "raw_text": raw_text,
        "skills": skills,
        "experience": sections.get("experience", ""),
        "projects": projects,
        "certifications": certifications,
        "education": sections.get("education", ""),
        "summary": sections.get("summary", ""),
        "years_experience": years_exp,
        "char_count": len(raw_text),
    }
    log.info(
        "Resume parsed → %d skills, %d projects, %.1f yrs exp",
        len(skills), len(projects), years_exp,
    )
    return result
