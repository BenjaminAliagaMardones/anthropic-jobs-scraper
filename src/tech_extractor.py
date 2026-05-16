"""Extract tech stack from job descriptions using Gemini, with regex fallback."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from tqdm import tqdm

# Curated tech dictionary for the regex fallback. Order matters only for display.
TECH_DICTIONARY = [
    # Languages
    "Python", "TypeScript", "JavaScript", "Go", "Rust", "C++", "C#", "Java",
    "Kotlin", "Swift", "Ruby", "Scala", "Haskell", "OCaml", "Bash", "SQL",
    # ML / AI  (note: "Transformers" removed — too many false positives with the
    # "transformer architecture" generic mention.)
    "PyTorch", "TensorFlow", "JAX", "Flax", "Triton", "CUDA", "XLA", "ONNX",
    "Hugging Face", "LangChain", "vLLM", "DeepSpeed",
    "Megatron", "Ray", "MLflow", "Weights & Biases", "Pandas", "NumPy",
    "SciPy", "scikit-learn", "Polars",
    # Web / Frontend
    "React", "Next.js", "Vue", "Svelte", "Angular", "Node.js", "Express",
    "FastAPI", "Flask", "Django", "GraphQL", "REST", "gRPC", "Tailwind",
    # Data / Infra
    "Kubernetes", "Docker", "Terraform", "Pulumi", "Helm", "Ansible",
    "Kafka", "Spark", "Airflow", "dbt", "Snowflake", "BigQuery", "Redshift",
    "Postgres", "PostgreSQL", "MySQL", "Redis", "MongoDB", "Elasticsearch",
    "ClickHouse", "DuckDB",
    # Cloud
    "AWS", "GCP", "Azure", "Cloudflare", "Vercel", "Datadog", "Grafana",
    "Prometheus", "OpenTelemetry",
    # Hardware / Systems
    "GPU", "TPU", "InfiniBand", "NCCL", "RDMA", "Linux",
    # Security
    "OAuth", "SAML", "Zero Trust", "SOC 2", "ISO 27001",
    # Tools
    "Git", "GitHub", "GitLab", "Jira", "Linear",
]

# Build a regex once. Match whole words / common boundaries (case-insensitive).
def _build_tech_pattern() -> re.Pattern:
    escaped = [re.escape(t) for t in TECH_DICTIONARY]
    # Use lookarounds to avoid matching "Go" inside "Google", etc.
    return re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )


_TECH_PATTERN = _build_tech_pattern()
_TECH_CANONICAL = {t.lower(): t for t in TECH_DICTIONARY}


def extract_with_regex(text: str) -> list[str]:
    found = set()
    for m in _TECH_PATTERN.finditer(text):
        key = m.group(1).lower()
        if key in _TECH_CANONICAL:
            found.add(_TECH_CANONICAL[key])
    # Normalize Postgres/PostgreSQL -> Postgres
    if "PostgreSQL" in found:
        found.discard("PostgreSQL")
        found.add("Postgres")
    return sorted(found)


# --- Gemini path ---

_GEMINI_PROMPT = """You are extracting technical skills from a job description.

Return ONLY a JSON array of strings with the names of programming languages,
frameworks, libraries, databases, cloud platforms, and tools EXPLICITLY mentioned
or strongly implied as required/used for the role. Use canonical names
(e.g. "PyTorch" not "pytorch", "Postgres" not "PostgreSQL"). Maximum 20 items.
Do NOT include soft skills, generic terms ("APIs", "ML"), or company names.

Job title: {title}

Description:
{description}

JSON array:"""


def _init_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        print(f"  [Gemini] init failed: {e}")
        return None


def _extract_with_gemini(model, title: str, description: str) -> list[str] | None:
    prompt = _GEMINI_PROMPT.format(title=title, description=description[:6000])
    try:
        resp = model.generate_content(prompt)
        raw = (resp.text or "").strip()
        # Strip code fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        # Find the first JSON array
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        return None
    return None


def extract_all(jobs: list[dict], use_llm: bool, cache_path: Path) -> list[dict]:
    """Annotate each job dict with a 'technologies' list. Caches by job id."""
    cache: dict[str, list[str]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except Exception:
            cache = {}

    model = _init_gemini() if use_llm else None
    if use_llm and model is None:
        print("  [Gemini] no API key or init failed -> falling back to regex.")
    elif use_llm:
        print("  [Gemini] model ready.")

    consecutive_failures = 0
    for job in tqdm(jobs, desc="Extracting tech"):
        key = str(job["id"])
        if key in cache:
            job["technologies"] = cache[key]
            continue

        techs: list[str] | None = None
        if model is not None and consecutive_failures < 5:
            techs = _extract_with_gemini(model, job["title"], job["description"])
            if techs is None:
                consecutive_failures += 1
            else:
                consecutive_failures = 0
            # Gentle rate limiting for free tier (~15 RPM)
            time.sleep(4.5)

        if not techs:
            techs = extract_with_regex(job["description"])

        job["technologies"] = techs
        cache[key] = techs
        # Persist after every job in case we crash mid-run.
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))

    if consecutive_failures >= 5:
        print("  [Gemini] too many consecutive failures, remaining jobs used regex.")
    return jobs
