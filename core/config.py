"""
Centralised configuration. All settings come from environment variables.
No hardcoded secrets anywhere in the codebase.

Streamlit Cloud compatibility notes:
  - load_dotenv() is a no-op on Cloud (no .env file); os.environ is populated
    by the st.secrets bridge in app.py before any module import.
  - CHROMA_DIR falls back to /tmp/chroma_db if the project-relative path is
    not writable (Cloud containers mount the repo as read-only for Git-tracked
    paths, but /tmp is always writable).
  - The log FileHandler is wrapped in try/except so a non-writable logs/ dir
    does not crash startup; console logging always works.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Pin to the absolute .env path so it always loads regardless of CWD.
# On Streamlit Cloud this file won't exist; load_dotenv() is a harmless no-op.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR  = BASE_DIR / "logs"


def _safe_chroma_dir() -> Path:
    """
    Return a writable ChromaDB directory.

    Preference order:
      1. CHROMA_PERSIST_DIR env var (explicit override)
      2. <project>/data/chroma_db  (local dev default)
      3. /tmp/chroma_db            (Streamlit Cloud fallback)
    """
    explicit = os.getenv("CHROMA_PERSIST_DIR", "").strip()
    candidates = [
        Path(explicit) if explicit else None,
        DATA_DIR / "chroma_db",
        Path("/tmp/chroma_db"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Verify we can actually write into the directory
            _probe = candidate / ".write_probe"
            _probe.touch()
            _probe.unlink()
            return candidate
        except OSError:
            continue
    # Last resort — /tmp must always be writable
    fallback = Path("/tmp/chroma_db")
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


CHROMA_DIR = _safe_chroma_dir()

# Ensure logs dir exists (best-effort; Cloud may not allow writes here)
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

# ── API Keys ──────────────────────────────────────────────────────────────────
# These are populated from:
#   - local .env (via load_dotenv above), OR
#   - os.environ injected by the st.secrets bridge in app.py (Streamlit Cloud)
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
HF_TOKEN: str          = os.getenv("HF_TOKEN", "")
RAPIDAPI_KEY: str      = os.getenv("RAPIDAPI_KEY", "")

# ── Models ────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_COLLECTION_RESUMES = "resumes"
CHROMA_COLLECTION_JOBS    = "jobs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def get_logger(name: str) -> logging.Logger:
    """Return a consistently configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Console — always available
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        # File — optional; silently skipped if logs/ is not writable (Cloud)
        try:
            fh = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except OSError:
            pass
    return logger
