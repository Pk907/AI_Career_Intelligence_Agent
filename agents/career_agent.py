"""
Career Intelligence Orchestrator.

DESIGN PRINCIPLE: the user's requested role (job_query) and location are
treated as explicit, authoritative inputs. They are logged at entry and
threaded through every downstream step unchanged. No step is allowed to
silently substitute a different role/location without that substitution
being logged and surfaced in the result dict.

Uses a simple sequential pipeline instead of full Smolagents tool-calling
(to avoid heavyweight LLM dependency for the orchestration layer itself).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, IO

from tools.resume_tool import analyse_resume
from tools.job_search import search_jobs
from tools.matching_tool import match_jobs, compute_aggregate_skill_gaps
from tools.roadmap_tool import build_roadmap
from core.rag_chain import generate_career_summary
from core.config import get_logger

log = get_logger(__name__)


class CareerAgent:
    """
    Orchestrates the full career intelligence pipeline.

    Step 1 → Resume Analysis
    Step 2 → Job Search (user's role + location)
    Step 3 → Job Matching + Scoring
    Step 4 → Skill Gap Analysis
    Step 5 → Career Roadmap Generation (target = user's role, not a job title)
    Step 6 → Career Summary (LLM / fallback)
    """

    def run(
        self,
        resume_source: str | Path | IO[bytes],
        job_query: str = "",
        job_location: str = "Remote India",
        timeline_weeks: int = 12,
        progress_callback=None,
    ) -> dict[str, Any]:
        """
        Run the full pipeline.

        Parameters
        ----------
        resume_source   : PDF file path or file-like object
        job_query       : User-requested role/keywords. AUTHORITATIVE —
                           used for job search AND as the roadmap target role.
                           Only replaced by an auto-derived value if blank.
        job_location    : User-requested location. AUTHORITATIVE — passed
                           verbatim to job search.
        timeline_weeks  : Learning roadmap horizon
        progress_callback : Optional callable(step: int, label: str)

        Returns
        -------
        dict with all pipeline outputs, plus:
          - requested_role        : what the user actually typed (or "" )
          - requested_location    : what the user actually typed
          - active_role           : the role actually used after fallback logic
          - active_location       : the location actually used
          - role_was_auto_derived : True if job_query was blank and we derived one
        """
        result: dict[str, Any] = {}
        errors: list[str] = []

        # ── Capture the raw user input BEFORE any mutation ────────────────────
        requested_role = (job_query or "").strip()
        requested_location = (job_location or "").strip()

        log.info(
            "PIPELINE START — requested_role=%r requested_location=%r timeline_weeks=%d",
            requested_role, requested_location, timeline_weeks,
        )

        def _progress(step: int, label: str) -> None:
            log.info("Step %d/6: %s", step, label)
            if progress_callback:
                progress_callback(step, label)

        # ── Step 1: Resume Analysis ───────────────────────────────────────────
        _progress(1, "Analysing resume…")
        try:
            resume_data = analyse_resume(resume_source)
            result["resume"] = resume_data
        except Exception as exc:
            errors.append(f"Resume analysis failed: {exc}")
            log.error("Resume analysis error: %s", exc)
            return {"errors": errors}

        # ── Step 2: Job Search ────────────────────────────────────────────────
        _progress(2, "Searching for relevant jobs…")

        role_was_auto_derived = False
        active_role = requested_role
        if not active_role:
            top_skills = resume_data.get("skills", [])[:4]
            active_role = " ".join(top_skills) or "software engineer"
            role_was_auto_derived = True
            log.info(
                "No role entered by user — auto-derived active_role=%r from resume skills",
                active_role,
            )

        active_location = requested_location or "Remote"

        log.info(
            "JOB SEARCH PARAMS SENT TO search_jobs() — role=%r location=%r",
            active_role, active_location,
        )

        try:
            jobs = search_jobs(active_role, location=active_location)
            result["raw_jobs"] = jobs
        except Exception as exc:
            errors.append(f"Job search failed: {exc}")
            jobs = []

        # ── Step 3: Job Matching ──────────────────────────────────────────────
        _progress(3, "Calculating match scores…")
        try:
            matched_jobs = match_jobs(resume_data, jobs, top_n=10)
            result["matched_jobs"] = matched_jobs
        except Exception as exc:
            errors.append(f"Job matching failed: {exc}")
            matched_jobs = []

        # ── Step 4: Skill Gap Analysis ────────────────────────────────────────
        _progress(4, "Identifying skill gaps…")
        try:
            skill_gaps = compute_aggregate_skill_gaps(resume_data, matched_jobs)
            result["skill_gaps"] = skill_gaps
        except Exception as exc:
            errors.append(f"Skill gap analysis failed: {exc}")
            skill_gaps = []

        # ── Step 5: Learning Roadmap ──────────────────────────────────────────
        # IMPORTANT: target_role is the user's active_role, NOT the top
        # matched job title. Using a matched job title here was the bug —
        # it silently discarded the user's actual request whenever the
        # static fallback job pool didn't contain a perfect match.
        _progress(5, "Generating learning roadmap…")
        log.info("ROADMAP TARGET ROLE — using active_role=%r (not a matched job title)", active_role)
        try:
            roadmap = build_roadmap(skill_gaps, active_role, timeline_weeks)
            result["roadmap"] = roadmap
        except Exception as exc:
            errors.append(f"Roadmap generation failed: {exc}")
            result["roadmap"] = {}

        # ── Step 6: Career Summary ────────────────────────────────────────────
        _progress(6, "Generating career intelligence summary…")
        try:
            summary = generate_career_summary(resume_data, matched_jobs, target_role=active_role)
            result["career_summary"] = summary
        except Exception as exc:
            errors.append(f"Career summary failed: {exc}")
            result["career_summary"] = self._rule_based_summary(resume_data, matched_jobs, active_role)

        # ── Surface exactly what was requested vs. what was used ─────────────
        result["requested_role"] = requested_role
        result["requested_location"] = requested_location
        result["active_role"] = active_role
        result["active_location"] = active_location
        result["role_was_auto_derived"] = role_was_auto_derived

        # Transparency: expose which backends actually served this run, so
        # the UI never implies a capability that wasn't really used.
        from core.vector_store import get_embedding_backend
        result["embedding_backend"] = get_embedding_backend()
        result["job_search_backend"] = "rapidapi-jsearch" if os.getenv("RAPIDAPI_KEY", "") else "fallback-demo-pool"
        result["llm_backend"] = (
            "anthropic-claude-sonnet-4-6" if os.getenv("ANTHROPIC_API_KEY", "")
            else "huggingface-inference" if os.getenv("HF_TOKEN", "")
            else "rule-based-fallback"
        )

        result["errors"] = errors
        result["pipeline_complete"] = True
        log.info(
            "PIPELINE COMPLETE — active_role=%r active_location=%r errors=%d",
            active_role, active_location, len(errors),
        )
        return result

    @staticmethod
    def _rule_based_summary(resume_data: dict, matched_jobs: list[dict], target_role: str) -> str:
        skills = ", ".join(resume_data.get("skills", [])[:6]) or "various technologies"
        yrs = resume_data.get("years_experience", 0)
        top_score = matched_jobs[0].get("match_score", 0) if matched_jobs else 0
        return (
            f"Candidate with {yrs} years experience and skills in {skills}, "
            f"evaluated against target role: {target_role}. "
            f"Top match score: {top_score:.0%}. "
            f"Focus on portfolio projects and targeted skill upgrades to maximise interview conversion."
        )


# Singleton
career_agent = CareerAgent()
