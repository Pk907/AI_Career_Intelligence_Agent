"""
Smolagents-compatible tool: Resume Analysis
Wraps the resume parser + vector store upsert in a single callable.
"""
from __future__ import annotations

from pathlib import Path
from typing import IO, Any

from core.resume_parser import parse_resume
from core.vector_store import upsert_resume, _resume_to_doc
from core.config import get_logger

log = get_logger(__name__)


def analyse_resume(source: str | Path | IO[bytes]) -> dict[str, Any]:
    """
    Full resume analysis pipeline.
    Input : PDF path or file-like object
    Output: structured dict + ChromaDB document ID
    """
    try:
        parsed = parse_resume(source)
        doc_id = upsert_resume(parsed)
        parsed["doc_id"] = doc_id
        parsed["resume_doc"] = _resume_to_doc(parsed)
        log.info("Resume analysis complete → doc_id=%s", doc_id)
        return parsed
    except Exception as exc:
        log.error("Resume analysis failed: %s", exc)
        raise
