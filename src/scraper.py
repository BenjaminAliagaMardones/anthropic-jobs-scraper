"""Scraper for Anthropic jobs via the public Greenhouse API."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true"

# Curated tech dictionary used to detect stack mentions in job descriptions.
TECH_DICTIONARY = [
    # Languages
    "Python", "TypeScript", "JavaScript", "Go", "Rust", "C++", "C#", "Java",
    "Kotlin", "Swift", "Ruby", "Scala", "Haskell", "OCaml", "Bash", "SQL",
    # ML / AI
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

_TECH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(t) for t in TECH_DICTIONARY) + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_TECH_CANONICAL = {t.lower(): t for t in TECH_DICTIONARY}


def extract_technologies(text: str) -> list[str]:
    found = set()
    for m in _TECH_PATTERN.finditer(text or ""):
        key = m.group(1).lower()
        if key in _TECH_CANONICAL:
            found.add(_TECH_CANONICAL[key])
    if "PostgreSQL" in found:
        found.discard("PostgreSQL")
        found.add("Postgres")
    return sorted(found)

ENGINEERING_DEPARTMENTS = {
    "AI Research & Engineering",
    "Applied AI",
    "Compute",
    "Engineering & Design - Product",
    "Security",
    "Software Engineering - Infrastructure",
    "Technical Program Management",
    "Technical Program Management ",  # trailing space exists in Greenhouse data
}

SALARY_PATTERNS = [
    re.compile(r"\$([\d,]+)\s*[—–\-‐‑to]+\s*\$?([\d,]+)\s*USD", re.IGNORECASE),
    re.compile(r"Annual Salary[:\s]*\$([\d,]+)\s*[—–\-‐‑to]+\s*\$?([\d,]+)", re.IGNORECASE),
]

SENIORITY_KEYWORDS = [
    ("Intern", ["intern", "fellow"]),
    ("Entry", ["entry-level", "associate", "junior"]),
    ("Mid", ["mid-level"]),
    ("Senior", ["senior", "sr."]),
    ("Staff", ["staff"]),
    ("Principal", ["principal"]),
    ("Lead", ["lead", "tech lead"]),
    ("Manager", ["manager", " head ", "head of"]),
    ("Director", ["director"]),
    ("VP", ["vp ", "vice president"]),
]


def html_to_text(raw_html: str) -> str:
    decoded = html.unescape(raw_html or "")
    soup = BeautifulSoup(decoded, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def extract_salary(text: str) -> tuple[int | None, int | None]:
    for pat in SALARY_PATTERNS:
        m = pat.search(text)
        if m:
            lo = int(m.group(1).replace(",", ""))
            hi = int(m.group(2).replace(",", ""))
            if 30_000 <= lo <= 2_000_000 and 30_000 <= hi <= 2_000_000:
                return lo, hi
    return None, None


def infer_seniority(title: str) -> str:
    t = f" {title.lower()} "
    for label, keys in SENIORITY_KEYWORDS:
        if any(k in t for k in keys):
            return label
    return "Unspecified"


def fetch_all_jobs() -> list[dict]:
    resp = requests.get(GREENHOUSE_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()["jobs"]


def filter_engineering(jobs: list[dict]) -> list[dict]:
    out = []
    for j in jobs:
        dept_names = {d.get("name", "").strip() for d in j.get("departments", [])}
        if dept_names & {d.strip() for d in ENGINEERING_DEPARTMENTS}:
            out.append(j)
    return out


def normalize_job(job: dict) -> dict:
    text = html_to_text(job.get("content", ""))
    salary_lo, salary_hi = extract_salary(text)
    departments = [d.get("name", "").strip() for d in job.get("departments", [])]
    offices = [o.get("name", "") for o in job.get("offices", [])]
    location = (job.get("location") or {}).get("name", "")
    location_type = next(
        (m["value"] for m in job.get("metadata", []) if m.get("name") == "Location Type"),
        None,
    )
    return {
        "id": job["id"],
        "title": job["title"],
        "url": job["absolute_url"],
        "departments": departments,
        "primary_department": departments[0] if departments else "Unknown",
        "location": location,
        "offices": offices,
        "location_type": location_type,
        "seniority": infer_seniority(job["title"]),
        "salary_min_usd": salary_lo,
        "salary_max_usd": salary_hi,
        "salary_mid_usd": (salary_lo + salary_hi) // 2 if salary_lo and salary_hi else None,
        "updated_at": job.get("updated_at"),
        "first_published": job.get("first_published"),
        "description": text,
        "technologies": extract_technologies(text),
    }


def scrape(output_path: Path) -> list[dict]:
    print("Fetching jobs from Greenhouse API...")
    raw = fetch_all_jobs()
    print(f"  Got {len(raw)} total jobs across all departments.")
    eng = filter_engineering(raw)
    print(f"  Filtered to {len(eng)} Engineering jobs.")
    normalized = [normalize_job(j) for j in eng]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False))
    print(f"  Saved raw data -> {output_path}")
    return normalized


def load(output_path: Path) -> list[dict]:
    return json.loads(output_path.read_text())
