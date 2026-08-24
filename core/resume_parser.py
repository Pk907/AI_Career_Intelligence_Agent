"""
Parses a PDF resume into structured data.

Key fixes (audit 2026-08-08):
- Skill extraction uses a whitelist + alias normalization; no raw delimiter splitting
  that previously picked up city names ("Pune"), common words ("programming"), etc.
- Skills are grouped into categories (Programming, AI/ML, Frameworks, etc.).
- Fresher display: years_experience=0 is exposed as 0.0, not None/empty.
- Experience text is extracted from the full raw text if no explicit section found.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import IO

from pypdf import PdfReader
from core.config import get_logger

log = get_logger(__name__)

# ── Section header patterns ───────────────────────────────────────────────────
_SECTION_PATTERNS = {
    "skills":         re.compile(r"(technical\s+skills?|skills?|core\s+competenc|technologies|tools)", re.I),
    "experience":     re.compile(r"(work\s+experience|experience|employment|professional\s+background)", re.I),
    "projects":       re.compile(r"(projects?|portfolio|notable\s+work)", re.I),
    "education":      re.compile(r"(education|academic|qualification|degree)", re.I),
    "certifications": re.compile(r"(certif|license|credential|award)", re.I),
    "summary":        re.compile(r"(summary|objective|profile|about)", re.I),
}

# ── Canonical skill whitelist with aliases ────────────────────────────────────
# Maps every known alias → canonical lowercase display name.
# This is the ONLY source of truth for skill detection.
_SKILL_ALIASES: dict[str, str] = {
    # Programming languages
    "python": "Python", "py": "Python",
    "java": "Java",
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#",
    "go": "Go", "golang": "Go",
    "rust": "Rust",
    "r": "R",
    "scala": "Scala",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "ruby": "Ruby",
    "shell": "Shell", "bash": "Shell", "bash scripting": "Shell",
    "powershell": "PowerShell",

    # AI / ML
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "natural language processing": "NLP", "nlp": "NLP",
    "computer vision": "Computer Vision", "cv": "Computer Vision",
    "llm": "LLM", "large language model": "LLM",
    "generative ai": "Generative AI", "gen ai": "Generative AI", "genai": "Generative AI",
    "rag": "RAG", "retrieval augmented generation": "RAG",
    "reinforcement learning": "Reinforcement Learning", "rl": "Reinforcement Learning",
    "mlops": "MLOps",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "feature engineering": "Feature Engineering",
    "prompt engineering": "Prompt Engineering",
    "fine-tuning": "Fine-Tuning", "fine tuning": "Fine-Tuning",
    "transfer learning": "Transfer Learning",

    # Frameworks / Libraries
    "pytorch": "PyTorch", "torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "keras": "Keras",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face", "hf": "Hugging Face",
    "transformers": "Transformers", "huggingface transformers": "Transformers",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex", "llama index": "LlamaIndex",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",
    "plotly": "Plotly",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "react": "React", "reactjs": "React",
    "vue": "Vue.js", "vuejs": "Vue.js",
    "angular": "Angular",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "spring": "Spring", "spring boot": "Spring Boot",
    "streamlit": "Streamlit",
    "gradio": "Gradio",
    "celery": "Celery",
    "pydantic": "Pydantic",
    "sqlalchemy": "SQLAlchemy",

    # Databases
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "neo4j": "Neo4j",
    "chromadb": "ChromaDB", "chroma": "ChromaDB",
    "pinecone": "Pinecone",
    "weaviate": "Weaviate",
    "qdrant": "Qdrant",
    "sqlite": "SQLite",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",
    "bigquery": "BigQuery",
    "snowflake": "Snowflake",
    "vector database": "Vector DB", "vector db": "Vector DB",

    # Cloud / DevOps
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "terraform": "Terraform",
    "airflow": "Airflow", "apache airflow": "Airflow",
    "spark": "Spark", "apache spark": "Spark",
    "kafka": "Kafka", "apache kafka": "Kafka",
    "hadoop": "Hadoop",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
    "github actions": "GitHub Actions",
    "jenkins": "Jenkins",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "sagemaker": "SageMaker",

    # Tools / Other
    "git": "Git",
    "linux": "Linux", "unix": "Linux",
    "rest": "REST API", "rest api": "REST API", "restful": "REST API",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "html": "HTML",
    "css": "CSS",
    "tailwind": "Tailwind CSS",
    "figma": "Figma",
    "agile": "Agile",
    "scrum": "Scrum",
}

# Canonical → category mapping for grouping
_SKILL_CATEGORIES: dict[str, str] = {
    "Python": "Programming", "Java": "Programming", "JavaScript": "Programming",
    "TypeScript": "Programming", "C++": "Programming", "C#": "Programming",
    "Go": "Programming", "Rust": "Programming", "R": "Programming",
    "Scala": "Programming", "Kotlin": "Programming", "Swift": "Programming",
    "PHP": "Programming", "Ruby": "Programming", "Shell": "Programming",
    "PowerShell": "Programming",

    "Machine Learning": "AI/ML", "Deep Learning": "AI/ML", "NLP": "AI/ML",
    "Computer Vision": "AI/ML", "LLM": "AI/ML", "Generative AI": "AI/ML",
    "RAG": "AI/ML", "Reinforcement Learning": "AI/ML", "MLOps": "AI/ML",
    "Data Science": "AI/ML", "Data Analysis": "AI/ML",
    "Feature Engineering": "AI/ML", "Prompt Engineering": "AI/ML",
    "Fine-Tuning": "AI/ML", "Transfer Learning": "AI/ML",

    "PyTorch": "Libraries", "TensorFlow": "Libraries", "Keras": "Libraries",
    "scikit-learn": "Libraries", "Hugging Face": "Libraries",
    "Transformers": "Libraries", "LangChain": "Libraries",
    "LlamaIndex": "Libraries", "OpenAI": "Libraries", "Anthropic": "Libraries",
    "Pandas": "Libraries", "NumPy": "Libraries", "SciPy": "Libraries",
    "Matplotlib": "Libraries", "Seaborn": "Libraries", "Plotly": "Libraries",
    "XGBoost": "Libraries", "LightGBM": "Libraries",

    "FastAPI": "Frameworks", "Flask": "Frameworks", "Django": "Frameworks",
    "React": "Frameworks", "Vue.js": "Frameworks", "Angular": "Frameworks",
    "Node.js": "Frameworks", "Spring": "Frameworks", "Spring Boot": "Frameworks",
    "Streamlit": "Frameworks", "Gradio": "Frameworks", "Celery": "Frameworks",
    "Pydantic": "Frameworks", "SQLAlchemy": "Frameworks",

    "SQL": "Databases", "MySQL": "Databases", "PostgreSQL": "Databases",
    "MongoDB": "Databases", "Redis": "Databases", "Elasticsearch": "Databases",
    "Neo4j": "Databases", "ChromaDB": "Databases", "Pinecone": "Databases",
    "Weaviate": "Databases", "Qdrant": "Databases", "SQLite": "Databases",
    "Cassandra": "Databases", "DynamoDB": "Databases", "BigQuery": "Databases",
    "Snowflake": "Databases", "Vector DB": "Databases",

    "AWS": "Cloud/DevOps", "GCP": "Cloud/DevOps", "Azure": "Cloud/DevOps",
    "Docker": "Cloud/DevOps", "Kubernetes": "Cloud/DevOps",
    "Terraform": "Cloud/DevOps", "Airflow": "Cloud/DevOps",
    "Spark": "Cloud/DevOps", "Kafka": "Cloud/DevOps", "Hadoop": "Cloud/DevOps",
    "CI/CD": "Cloud/DevOps", "GitHub Actions": "Cloud/DevOps",
    "Jenkins": "Cloud/DevOps", "MLflow": "Cloud/DevOps",
    "Kubeflow": "Cloud/DevOps", "SageMaker": "Cloud/DevOps",

    "Git": "Tools", "Linux": "Tools", "REST API": "Tools",
    "GraphQL": "Tools", "gRPC": "Tools", "HTML": "Tools",
    "CSS": "Tools", "Tailwind CSS": "Tools", "Figma": "Tools",
    "Agile": "Tools", "Scrum": "Tools",
}

# Words that must NEVER be treated as skills
_SKILL_BLOCKLIST = {
    # Cities / countries
    "pune", "mumbai", "bangalore", "bengaluru", "delhi", "hyderabad",
    "chennai", "kolkata", "india", "remote", "maharashtra", "karnataka",
    "usa", "uk", "canada", "australia", "singapore",
    # Generic words
    "programming", "development", "engineering", "skills", "tools",
    "experience", "work", "project", "projects", "team", "using",
    "knowledge", "understanding", "proficiency", "ability", "strong",
    "good", "excellent", "etc", "and", "or", "the", "with", "for",
    "including", "various", "multiple", "different", "new", "latest",
    "good knowledge", "strong knowledge", "proficient in",
    # Education
    "b.tech", "m.tech", "btech", "mtech", "bsc", "msc", "bachelor",
    "master", "phd", "university", "college", "institute",
    # Misc
    "github", "linkedin", "portfolio", "email", "phone", "address",
    "references", "hobbies", "interests",
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
    """Split raw resume text into named sections using header heuristics."""
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


def _normalise_skill(raw: str) -> str | None:
    """
    Return the canonical display name for a raw skill string, or None if not recognized.
    Uses the alias map; blocklist filters noise.
    """
    clean = raw.strip().lower()
    # Remove trailing punctuation
    clean = re.sub(r"[^\w\s#+./]", "", clean).strip()

    if not clean or clean in _SKILL_BLOCKLIST:
        return None
    if len(clean) < 2 or len(clean) > 50:
        return None

    # Direct alias lookup
    if clean in _SKILL_ALIASES:
        return _SKILL_ALIASES[clean]

    # Partial match: check if any alias is a substring (for multi-word skills)
    for alias, canonical in _SKILL_ALIASES.items():
        if alias == clean:
            return canonical

    return None


def extract_skills(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """
    Extract and normalize skills from text.

    Returns:
        flat_skills: deduplicated canonical skill names
        grouped:     dict of category → [skill names]
    """
    found: dict[str, str] = {}  # canonical → category

    lower = text.lower()

    # Pass 1: scan for all known aliases in the full text
    for alias, canonical in _SKILL_ALIASES.items():
        # Use lookbehind and lookahead to match word boundaries safely,
        # even for skills like C++ or C# that end in non-word characters.
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if re.search(pattern, lower):
            if canonical not in found:
                found[canonical] = _SKILL_CATEGORIES.get(canonical, "Other")

    # Build outputs
    flat_skills = list(found.keys())
    grouped: dict[str, list[str]] = {}
    for skill, category in found.items():
        grouped.setdefault(category, []).append(skill)

    # Sort categories in preferred order
    cat_order = ["Programming", "AI/ML", "Libraries", "Frameworks", "Databases", "Cloud/DevOps", "Tools", "Other"]
    grouped_sorted = {cat: sorted(grouped[cat]) for cat in cat_order if cat in grouped}
    # Append any unexpected categories
    for cat in grouped:
        if cat not in grouped_sorted:
            grouped_sorted[cat] = sorted(grouped[cat])

    log.info("Skills extracted: %d total across %d categories", len(flat_skills), len(grouped_sorted))
    return flat_skills, grouped_sorted


def _extract_years_of_experience(experience_text: str, full_text: str = "") -> float:
    """
    Estimate years of experience from date ranges.
    Looks for patterns like 2021-2023, Jan 2022 – Present, etc.
    Returns 0.0 for freshers (no work history found).
    """
    search_text = experience_text or full_text
    year_pattern = re.compile(r"\b(20\d{2}|19\d{2})\b")
    years_found = [int(y) for y in year_pattern.findall(search_text)]

    # Filter: exclude graduation years if they're the only ones (education section)
    # A very rough heuristic: if >= 2 different years, compute span
    unique_years = sorted(set(years_found))
    if len(unique_years) >= 2:
        span = max(unique_years) - min(unique_years)
        # Cap at 40 years to avoid education year artifacts
        return round(min(span, 40), 1)
    return 0.0


def _extract_projects(projects_text: str) -> list[str]:
    """Pull project titles from the projects section."""
    projects = []
    for line in projects_text.splitlines():
        line = line.strip()
        if line and len(line) < 100 and not line[0].islower():
            # Skip lines that are clearly descriptions (contain common verbs)
            if not re.search(r"^(built|created|developed|implemented|used|using|with|the|a )", line, re.I):
                projects.append(line)
    return projects[:10]


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

    Returns dict with keys:
        raw_text, skills, skill_groups, experience, projects,
        certifications, education, summary, years_experience
    """
    raw_text = extract_text_from_pdf(source)
    sections = _split_into_sections(raw_text)

    # Skills: search skills section first, then full text
    skills_text = sections.get("skills", "") + "\n" + raw_text
    flat_skills, skill_groups = extract_skills(skills_text)

    # Experience
    exp_text = sections.get("experience", "")
    years_exp = _extract_years_of_experience(exp_text, raw_text)

    projects = _extract_projects(sections.get("projects", ""))
    certifications = _extract_certifications(sections.get("certifications", ""))

    result = {
        "raw_text":         raw_text,
        "skills":           flat_skills,
        "skill_groups":     skill_groups,   # NEW: grouped skills dict
        "experience":       exp_text,
        "projects":         projects,
        "certifications":   certifications,
        "education":        sections.get("education", ""),
        "summary":          sections.get("summary", ""),
        "years_experience": years_exp,      # 0.0 for freshers, never None
        "is_fresher":       years_exp == 0.0,
        "char_count":       len(raw_text),
    }
    log.info(
        "Resume parsed → %d skills (%d categories), %d projects, %.1f yrs exp, fresher=%s",
        len(flat_skills), len(skill_groups), len(projects), years_exp, result["is_fresher"],
    )
    return result
