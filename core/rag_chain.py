"""
RAG-style prompt construction and LLM dispatch.

NOTE: this module does NOT use the LangChain library. It hand-constructs
prompts and calls the Anthropic / HF Inference APIs directly. An earlier
version of this docstring claimed LangChain — that was inaccurate and has
been corrected. If you want to genuinely use LangChain's chain/retriever
abstractions, swap this module's internals for langchain's
ConversationalRetrievalChain or similar; right now it's plain Python.

LLM backend priority:
  1. Anthropic claude-sonnet-4-6  (if ANTHROPIC_API_KEY is set)
  2. Hugging Face Inference API   (if HF_TOKEN is set)
  3. Rule-based fallback          (always works, no API required)
"""
from __future__ import annotations

import os
import re
from core.config import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LLM call dispatch
# ─────────────────────────────────────────────────────────────────────────────

def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _call_hf(prompt: str, model: str = "mistralai/Mistral-7B-Instruct-v0.3") -> str:
    import requests
    hf_token = os.getenv("HF_TOKEN", "")
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 512, "temperature": 0.3},
    }
    resp = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, list) and result:
        text = result[0].get("generated_text", "")
        # Strip the prompt from the output
        return text[len(prompt):].strip() if text.startswith(prompt) else text.strip()
    return str(result)


def _llm_call(prompt: str) -> str | None:
    """Try available LLM backends. Returns None if all fail."""
    if os.getenv("ANTHROPIC_API_KEY", ""):
        try:
            return _call_anthropic(prompt)
        except Exception as exc:
            log.error("Anthropic call failed: %s", exc)

    if os.getenv("HF_TOKEN", ""):
        try:
            return _call_hf(prompt)
        except Exception as exc:
            log.error("HF Inference call failed: %s", exc)

    return None


def _build_prompt(context: str, question: str) -> str:
    return (
        "You are a career intelligence assistant. Use ONLY the context below "
        "to answer the question. Be specific, concise, and actionable.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION:\n{question}\n\n"
        "ANSWER:"
    )


def run_rag_query(question: str, context_docs: list[str]) -> str:
    context = "\n\n---\n\n".join(context_docs[:5])
    prompt  = _build_prompt(context, question)
    result  = _llm_call(prompt)
    if result:
        return result
    log.info("No LLM available – using rule-based fallback answer")
    return f"[No LLM configured – add ANTHROPIC_API_KEY or HF_TOKEN for AI insights]\n\n{context[:600]}"


# ─────────────────────────────────────────────────────────────────────────────
# Named RAG tasks
# ─────────────────────────────────────────────────────────────────────────────

def generate_career_summary(
    parsed_resume: dict,
    matched_jobs: list[dict],
    target_role: str = "",
) -> str:
    skills_str  = ", ".join(parsed_resume.get("skills", [])[:20])
    job_titles  = [j["meta"].get("title", "") if "meta" in j else j.get("title","") for j in matched_jobs[:5]]
    role_line   = f"Target role (user-specified): {target_role}\n" if target_role else ""
    context = (
        f"{role_line}"
        f"Candidate skills: {skills_str}\n"
        f"Years of experience: {parsed_resume.get('years_experience', 0)}\n"
        f"Top matched jobs against this target: {', '.join(job_titles)}\n"
        f"Projects: {'; '.join(parsed_resume.get('projects', [])[:3])}\n"
        f"Certifications: {'; '.join(parsed_resume.get('certifications', [])[:3])}"
    )
    question = (
        f"Summarise this candidate's fit for the role '{target_role}' in 3-4 sentences "
        f"and identify their strongest positioning angle for that specific role."
        if target_role else
        "Summarise this candidate's career profile in 3-4 sentences and identify "
        "their strongest career positioning angle."
    )
    result = run_rag_query(question, [context])
    if result.startswith("[No LLM"):
        return _rule_career_summary(parsed_resume, matched_jobs, target_role)
    return result


def _rule_career_summary(parsed_resume: dict, matched_jobs: list[dict], target_role: str = "") -> str:
    skills = ", ".join(parsed_resume.get("skills", [])[:6]) or "software development"
    yrs    = parsed_resume.get("years_experience", 0)
    projs  = len(parsed_resume.get("projects", []))
    score  = matched_jobs[0].get("match_score", 0) if matched_jobs else 0
    role_phrase = f"against target role '{target_role}'" if target_role else ""
    return (
        f"Candidate with {yrs:.0f} years experience, proficient in {skills}. "
        f"Built {projs} tracked project(s) — strong foundation for portfolio-first job search. "
        f"Best semantic match {role_phrase}: {score:.0%}. "
        f"Add API keys (ANTHROPIC_API_KEY or HF_TOKEN) for personalised AI analysis."
    )


def generate_skill_gap_analysis(
    resume_skills: list[str],
    job_requirements: list[str],
    job_title: str,
) -> str:
    resume_set = {s.lower() for s in resume_skills}
    job_set    = {s.lower() for s in job_requirements}
    missing    = sorted(job_set - resume_set)
    present    = sorted(resume_set & job_set)
    context = (
        f"Job title: {job_title}\n"
        f"Skills the candidate HAS: {', '.join(present) or 'none matched'}\n"
        f"Skills the candidate is MISSING: {', '.join(missing) or 'none'}\n"
    )
    question = (
        "What are the top 5 skills the candidate should learn first to land this role, "
        "and why? Be direct and prioritise by impact."
    )
    return run_rag_query(question, [context])


def generate_learning_roadmap(
    skill_gaps: list[str],
    target_role: str,
    timeline_weeks: int = 12,
) -> str:
    context = (
        f"Target role: {target_role}\n"
        f"Skills to learn: {', '.join(skill_gaps[:10])}\n"
        f"Available time: {timeline_weeks} weeks\n"
    )
    question = (
        f"Create a week-by-week learning roadmap to fill these skill gaps for a "
        f"{target_role} role in {timeline_weeks} weeks. Include specific free resources. "
        "Be concrete and realistic."
    )
    return run_rag_query(question, [context])
