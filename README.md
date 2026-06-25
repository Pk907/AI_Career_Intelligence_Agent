# Career Intelligence Agent

A resume analysis and job-matching tool with two execution modes: a deterministic
pipeline, and a real LLM tool-calling agent built on `smolagents`.

This README is deliberately specific about what's real versus what degrades
gracefully, because the gap between "what a project claims" and "what it does"
is exactly what gets exposed in a technical interview.

## Two modes, and why both exist

**Deterministic Pipeline** — six tools called in a fixed order: parse resume →
search jobs → score matches → find skill gaps → build roadmap → summarise.
No LLM required to run. Fast, free, predictable. This is NOT an agent — it's
a pipeline. Calling it "agentic" would be the same kind of overclaim this
project is trying to avoid.

**Smolagents mode** — a real `ToolCallingAgent` from the `smolagents` library
receives a natural-language task and decides for itself which tools to call,
in what order, based on what it sees back from earlier calls. This requires
an `ANTHROPIC_API_KEY`. There is intentionally no rule-based fallback for
this mode — a tool-calling agent with no LLM isn't a degraded agent, it's
not an agent. If you run this mode, check the **Agent Trace** tab — it shows
the literal sequence of tool calls the model made. That trace is your proof
this is real, and it's also a good place to look if you're asked "how do you
know the agent isn't just hardcoded" in an interview.

## What's genuinely real vs. what falls back, and when

| Component | Best case | Fallback (when it triggers) |
|---|---|---|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (real semantic vectors) | TF-IDF + TruncatedSVD, local, no network — triggers if HuggingFace is unreachable |
| Job search | Live results via JSearch (RapidAPI) | Static 8-job demo pool, ranked by keyword overlap with your query — triggers with no `RAPIDAPI_KEY` |
| LLM reasoning (Deterministic mode) | Anthropic Claude or HF Inference generates the summary/roadmap text | Rule-based string templates — triggers with no API key |
| LLM reasoning (Smolagents mode) | Real ToolCallingAgent loop | **None** — raises `SmolagentUnavailableError` if no key |

The app's **Overview tab shows colored pills** (green = real backend active,
orange = fallback active) for every run, so you never have to guess which
path served your results. If you're demoing this, screenshot that pill row —
it's the single fastest way to prove to a skeptical interviewer that you know
exactly what your own system is doing.

## Known limitations — read before claiming this on a resume

- The fallback job pool has 8 hardcoded demo postings. Get a free RapidAPI
  key (JSearch API has a free tier) before treating job search results as real.
- TF-IDF embeddings are noticeably weaker than MiniLM for cross-domain
  matching (e.g. matching "backend engineer" resume language against an
  "AI Engineer" job description with different vocabulary). If your network
  blocks HuggingFace, you're on the weaker path — know this before you demo it.
- The Smolagents tool-calling loop has been verified to construct correctly
  and fail loudly without a key, but has **not** been verified against a live
  Anthropic API call in the environment this was built in (no API key was
  available there). Test it yourself with your own key before relying on it.
- PDF resume parsing uses regex/heuristic section detection, not an NER model.
  Resumes with unconventional formatting (no clear section headers, heavy
  use of tables/columns) will parse poorly. Check the extracted skills/projects
  in the Skills tab before trusting the downstream analysis.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add ANTHROPIC_API_KEY (required for Smolagents mode, optional but
# recommended for Deterministic mode) and RAPIDAPI_KEY (for real job search)
bash run.sh
```

## Architecture

```
core/
  resume_parser.py    — PDF → structured text (regex/heuristic section split)
  vector_store.py     — embeddings (MiniLM or TF-IDF fallback) + ChromaDB
  rag_chain.py         — hand-rolled prompt construction + Anthropic/HF dispatch
                          (does NOT use the LangChain library, despite the name)
  config.py            — env var loading, logging

tools/                 — plain Python functions, the actual business logic
  job_search.py
  matching_tool.py
  roadmap_tool.py
  resume_tool.py

agents/
  career_agent.py             — Deterministic Pipeline orchestrator
  smolagent_tools.py           — @tool-decorated wrappers for the agent
  smolagent_orchestrator.py    — real ToolCallingAgent setup and run()

app.py                 — Streamlit UI, both modes
```

## If you're presenting this in an interview

Be ready to explain, honestly:
1. Why resume PDF parsing is NOT a tool the agent calls (file I/O is
   deterministic preprocessing, not a decision worth LLM judgment).
2. What happens when `ANTHROPIC_API_KEY` is missing in each mode, and why
   the two modes handle that differently on purpose.
3. The TF-IDF fallback — what it is, why it's there, and that you know it's
   weaker than real sentence embeddings.
4. Walk through one real Agent Trace from a live run, not a description of
   what it would theoretically do.
