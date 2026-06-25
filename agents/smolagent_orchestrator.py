"""
Real Smolagents agent orchestrator.

This is what was missing before: an actual ToolCallingAgent that receives a
goal in natural language, decides which tools to call and in what order, and
produces a final answer — not a hand-written sequential pipeline pretending
to be "agentic."

Requires an LLM. Without ANTHROPIC_API_KEY set, this module raises clearly
rather than silently degrading to a fake agent — a tool-calling agent with
no LLM isn't a degraded agent, it's not an agent at all.
"""
from __future__ import annotations

import os
from typing import Any

from smolagents import ToolCallingAgent, LiteLLMModel

from agents.smolagent_tools import ALL_AGENT_TOOLS, set_active_resume
from core.config import get_logger

log = get_logger(__name__)


class SmolagentUnavailableError(RuntimeError):
    """Raised when no LLM is configured — a tool-calling agent cannot run without one."""


def _build_model() -> LiteLLMModel:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise SmolagentUnavailableError(
            "ANTHROPIC_API_KEY is not set. A ToolCallingAgent requires an LLM "
            "to decide which tools to call — there is no rule-based fallback "
            "for this step, by design. Set the key in .env or the sidebar."
        )
    # LiteLLM routes "anthropic/<model>" to the Anthropic API directly.
    return LiteLLMModel(model_id="anthropic/claude-sonnet-4-6", api_key=api_key)


def run_career_agent(
    resume_data: dict[str, Any],
    role: str,
    location: str,
    timeline_weeks: int = 12,
    max_steps: int = 8,
) -> dict[str, Any]:
    """
    Run a real tool-calling agent over the candidate's resume to produce
    job matches, skill gaps, and a learning roadmap.

    Parameters
    ----------
    resume_data     : parsed resume dict (from core.resume_parser.parse_resume)
    role            : user-requested target role — authoritative, passed
                      directly into the agent's task prompt
    location        : user-requested location — authoritative
    timeline_weeks  : roadmap horizon
    max_steps       : cap on agent tool-call steps, to bound cost/latency

    Returns
    -------
    dict with: final_answer (str), steps (list of tool calls made, for
    transparency/debugging), model_id used.
    """
    log.info(
        "SMOLAGENT RUN START — role=%r location=%r timeline_weeks=%d",
        role, location, timeline_weeks,
    )

    set_active_resume(resume_data)
    model = _build_model()

    agent = ToolCallingAgent(
        tools=ALL_AGENT_TOOLS,
        model=model,
        max_steps=max_steps,
    )

    task = (
        f"A candidate is targeting the role '{role}' in location '{location}'. "
        f"Their resume is already loaded — call get_active_resume_summary_tool "
        f"to see their skills and experience. "
        f"1) Search for matching jobs using search_jobs_tool with role='{role}' "
        f"and location='{location}'. "
        f"2) Score the resume against those jobs using match_resume_to_jobs_tool. "
        f"3) Run skill_gap_analysis_tool on the matched jobs. "
        f"4) Build a {timeline_weeks}-week learning roadmap for target_role='{role}' "
        f"using build_learning_roadmap_tool. "
        f"Finish by summarising: the top 3 job matches with their scores, the "
        f"top 5 skill gaps, and the headline of the learning roadmap. Be specific "
        f"and use the actual data returned by the tools — do not invent numbers."
    )

    try:
        result = agent.run(task)
    except Exception as exc:
        log.error("Smolagent run failed: %s", exc)
        raise

    # Extract the tool-call trace for transparency — useful for debugging
    # and for proving to a skeptical interviewer that this is a real agent loop.
    steps_trace = []
    memory = getattr(agent, "memory", None)
    for step in (memory.steps if memory else []):
        for tc in (getattr(step, "tool_calls", None) or []):
            steps_trace.append({"tool": tc.name, "arguments": tc.arguments})

    log.info("SMOLAGENT RUN COMPLETE — %d tool calls made", len(steps_trace))

    return {
        "final_answer": str(result),
        "steps": steps_trace,
        "model_id": "anthropic/claude-sonnet-4-6",
    }
