"""
Smolagents Tool definitions.

DESIGN NOTE — read this before assuming these are decorative:
PDF parsing is NOT a smolagents tool. Handing a CodeAgent/ToolCallingAgent a raw
PDF binary to "decide what to do with" is not how production agent systems are
built — file I/O and OCR/text extraction are deterministic preprocessing steps,
not actions worth LLM judgment. Real agent value lives in steps that require
reasoning over already-extracted data: which jobs are worth pursuing, what gaps
matter most, how to sequence learning. That's what's wired into the agent below.

Each tool here is a thin wrapper around the existing core/tools logic, exposed
with typed signatures and Google-style docstrings so smolagents' @tool decorator
can build a correct JSON schema for the underlying LLM to call.
"""
from __future__ import annotations

import json

from smolagents import tool

from tools.job_search import search_jobs as _search_jobs_impl
from tools.matching_tool import match_jobs as _match_jobs_impl
from tools.matching_tool import compute_aggregate_skill_gaps as _skill_gaps_impl
from tools.roadmap_tool import build_roadmap as _build_roadmap_impl
from core.config import get_logger

log = get_logger(__name__)

# Module-level state the tools read/write. Smolagents tools must be plain
# functions with JSON-serialisable args — they can't carry a resume PDF as
# an argument. We inject the parsed resume once per agent run via
# `set_active_resume()`, then tools reference it implicitly. This mirrors how
# production agent tools read from a session/request context rather than
# having every fact passed as a literal argument.
_ACTIVE_RESUME: dict = {}


def set_active_resume(resume_data: dict) -> None:
    """Bind the current candidate's parsed resume data for this agent run."""
    global _ACTIVE_RESUME
    _ACTIVE_RESUME = resume_data
    log.info(
        "Active resume bound to agent context — %d skills, %.1f yrs exp",
        len(resume_data.get("skills", [])), resume_data.get("years_experience", 0),
    )


@tool
def search_jobs_tool(role: str, location: str) -> str:
    """
    Search for job postings matching a role and location.

    Args:
        role: The job title or role keywords to search for, e.g. "Python Developer".
        location: The target location, e.g. "Remote India" or "Bangalore".

    Returns:
        A JSON string containing a list of job postings with title, company,
        location, description, required_skills, url, and salary.
    """
    log.info("AGENT TOOL CALL — search_jobs_tool(role=%r, location=%r)", role, location)
    jobs = _search_jobs_impl(role, location=location)
    return json.dumps(jobs)


@tool
def match_resume_to_jobs_tool(jobs_json: str) -> str:
    """
    Score the active candidate's resume against a list of jobs using semantic
    similarity, returning matched and missing skills per job.

    Args:
        jobs_json: A JSON string containing a list of job postings, as returned
            by search_jobs_tool.

    Returns:
        A JSON string containing the same jobs, ranked by match_score (0-1),
        each annotated with matched_skills, missing_skills, and match_tier.
    """
    log.info("AGENT TOOL CALL — match_resume_to_jobs_tool(%d bytes input)", len(jobs_json))
    jobs = json.loads(jobs_json)
    matched = _match_jobs_impl(_ACTIVE_RESUME, jobs, top_n=10)
    return json.dumps(matched)


@tool
def skill_gap_analysis_tool(matched_jobs_json: str) -> str:
    """
    Aggregate skill gaps across a set of matched jobs to find which missing
    skills appear most frequently and matter most for the candidate's target roles.

    Args:
        matched_jobs_json: A JSON string of matched jobs, as returned by
            match_resume_to_jobs_tool.

    Returns:
        A JSON string containing a ranked list of {skill, frequency,
        avg_job_score, priority} dicts, highest priority first.
    """
    log.info("AGENT TOOL CALL — skill_gap_analysis_tool(%d bytes input)", len(matched_jobs_json))
    matched_jobs = json.loads(matched_jobs_json)
    gaps = _skill_gaps_impl(_ACTIVE_RESUME, matched_jobs)
    return json.dumps(gaps)


@tool
def build_learning_roadmap_tool(skill_gaps_json: str, target_role: str, timeline_weeks: int) -> str:
    """
    Build a week-by-week learning roadmap to close the candidate's skill gaps
    for a specific target role.

    Args:
        skill_gaps_json: A JSON string of skill gaps, as returned by
            skill_gap_analysis_tool.
        target_role: The role the candidate is preparing for, e.g. "AI Engineer".
        timeline_weeks: Number of weeks available for the learning plan.

    Returns:
        A JSON string containing the roadmap: target_role, timeline_weeks,
        a week-by-week plan, and learning resources per skill.
    """
    log.info(
        "AGENT TOOL CALL — build_learning_roadmap_tool(target_role=%r, weeks=%d)",
        target_role, timeline_weeks,
    )
    gaps = json.loads(skill_gaps_json)
    roadmap = _build_roadmap_impl(gaps, target_role, timeline_weeks, use_llm=False)
    return json.dumps(roadmap)


@tool
def get_active_resume_summary_tool() -> str:
    """
    Return a summary of the candidate's currently active resume — their
    skills, years of experience, projects, and certifications.

    Returns:
        A JSON string with the candidate's skills, years_experience,
        projects, and certifications.
    """
    log.info("AGENT TOOL CALL — get_active_resume_summary_tool()")
    summary = {
        "skills": _ACTIVE_RESUME.get("skills", []),
        "years_experience": _ACTIVE_RESUME.get("years_experience", 0),
        "projects": _ACTIVE_RESUME.get("projects", []),
        "certifications": _ACTIVE_RESUME.get("certifications", []),
    }
    return json.dumps(summary)


ALL_AGENT_TOOLS = [
    get_active_resume_summary_tool,
    search_jobs_tool,
    match_resume_to_jobs_tool,
    skill_gap_analysis_tool,
    build_learning_roadmap_tool,
]
