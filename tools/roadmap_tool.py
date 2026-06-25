"""
Career roadmap generation tool.
Produces a structured, week-by-week learning plan.
"""
from __future__ import annotations

from core.rag_chain import generate_learning_roadmap, generate_skill_gap_analysis
from core.config import get_logger

log = get_logger(__name__)

# Curated free resource map for common skill gaps
_RESOURCES: dict[str, list[str]] = {
    "python": ["https://docs.python.org/3/tutorial/", "https://realpython.com"],
    "fastapi": ["https://fastapi.tiangolo.com/tutorial/", "https://testdriven.io/courses/tdd-fastapi/"],
    "flask": ["https://flask.palletsprojects.com/tutorial/"],
    "django": ["https://docs.djangoproject.com/en/stable/intro/tutorial01/"],
    "docker": ["https://docs.docker.com/get-started/", "https://labs.play-with-docker.com/"],
    "kubernetes": ["https://kubernetes.io/docs/tutorials/", "https://www.katacoda.com/courses/kubernetes"],
    "aws": ["https://aws.amazon.com/training/", "https://acloudguru.com/course/aws-certified-cloud-practitioner"],
    "gcp": ["https://cloud.google.com/training/", "https://cloudskillsboost.google/"],
    "azure": ["https://learn.microsoft.com/en-us/training/azure/"],
    "pytorch": ["https://pytorch.org/tutorials/", "https://course.fast.ai/"],
    "tensorflow": ["https://www.tensorflow.org/learn"],
    "scikit-learn": ["https://scikit-learn.org/stable/tutorial/", "https://kaggle.com/learn"],
    "langchain": ["https://python.langchain.com/docs/get_started/", "https://learn.deeplearning.ai/"],
    "hugging face": ["https://huggingface.co/learn", "https://huggingface.co/course/chapter1/1"],
    "mlops": ["https://mlops.community/", "https://github.com/visenger/awesome-mlops"],
    "sql": ["https://sqlbolt.com/", "https://mode.com/sql-tutorial/"],
    "mongodb": ["https://university.mongodb.com/", "https://learn.mongodb.com/"],
    "spark": ["https://spark.apache.org/docs/latest/", "https://databricks.com/learn"],
    "kafka": ["https://developer.confluent.io/learn-kafka/"],
    "airflow": ["https://airflow.apache.org/docs/apache-airflow/stable/tutorial/"],
    "react": ["https://react.dev/learn", "https://fullstackopen.com/en/"],
    "git": ["https://learngitbranching.js.org/", "https://git-scm.com/book/en/v2"],
    "linux": ["https://linuxjourney.com/", "https://overthewire.org/wargames/bandit/"],
    "nlp": ["https://www.nltk.org/book/", "https://course.spacy.io/en/"],
    "deep learning": ["https://course.fast.ai/", "https://d2l.ai/"],
    "machine learning": ["https://cs229.stanford.edu/", "https://www.kaggle.com/learn/intro-to-machine-learning"],
}


def build_roadmap(
    skill_gaps: list[dict],
    target_role: str,
    timeline_weeks: int = 12,
    use_llm: bool = True,
) -> dict:
    """
    Build a structured learning roadmap.

    Returns
    -------
    dict with:
      - weeks: list of weekly milestones
      - resources: skill → resource URLs
      - llm_narrative: LLM-generated narrative (if API key set)
    """
    top_gaps = [g["skill"] for g in skill_gaps[:8]]
    log.info(
        "BUILD ROADMAP — target_role=%r timeline_weeks=%d top_gaps=%s",
        target_role, timeline_weeks, top_gaps,
    )

    # Build weekly plan
    weeks = _build_weekly_plan(top_gaps, timeline_weeks)

    # Gather resource links
    resources = {
        skill: _RESOURCES.get(skill, ["https://www.google.com/search?q=learn+" + skill.replace(" ", "+")])
        for skill in top_gaps
    }

    # LLM narrative
    narrative = ""
    if use_llm:
        try:
            narrative = generate_learning_roadmap(top_gaps, target_role, timeline_weeks)
        except Exception as exc:
            log.error("LLM roadmap generation failed: %s", exc)
            narrative = _fallback_narrative(top_gaps, target_role, timeline_weeks)
    else:
        narrative = _fallback_narrative(top_gaps, target_role, timeline_weeks)

    return {
        "target_role": target_role,
        "timeline_weeks": timeline_weeks,
        "skill_gaps": top_gaps,
        "weeks": weeks,
        "resources": resources,
        "narrative": narrative,
    }


def _build_weekly_plan(skills: list[str], total_weeks: int) -> list[dict]:
    """Distribute skills across weeks."""
    if not skills:
        return []

    weeks_per_skill = max(1, total_weeks // max(len(skills), 1))
    plan = []
    week_num = 1

    for skill in skills:
        end_week = min(week_num + weeks_per_skill - 1, total_weeks)
        plan.append({
            "week_range": f"Week {week_num}–{end_week}",
            "focus": skill.title(),
            "goal": f"Build working proficiency in {skill}",
            "deliverable": f"Complete a small project or tutorial using {skill}",
            "resources": _RESOURCES.get(
                skill,
                [f"https://www.google.com/search?q=learn+{skill.replace(' ', '+')}"]
            ),
        })
        week_num = end_week + 1
        if week_num > total_weeks:
            break

    if week_num <= total_weeks:
        plan.append({
            "week_range": f"Week {week_num}–{total_weeks}",
            "focus": "Portfolio & Applications",
            "goal": "Build a capstone project combining learned skills",
            "deliverable": "Deploy a project to GitHub + apply to 10+ jobs",
            "resources": ["https://github.com", "https://linkedin.com"],
        })

    return plan


def _fallback_narrative(skills: list[str], role: str, weeks: int) -> str:
    if not skills:
        return f"Your resume already aligns well with {role} roles. Focus on applying."
    top3 = ", ".join(skills[:3])
    return (
        f"To land a {role} role in {weeks} weeks, prioritise: {top3}. "
        f"Spend the first half building fundamentals through tutorials and the second half "
        f"on a real project you can show in interviews. "
        f"Apply to jobs from week 4 onwards — don't wait until you feel 'ready'."
    )
