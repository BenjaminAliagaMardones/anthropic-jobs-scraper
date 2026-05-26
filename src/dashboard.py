"""Render a static HTML dashboard from the scraped jobs."""
from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

# Department -> (short label, subtitle)
DEPT_META = {
    "AI Research & Engineering":            ("Research",      "Frontier model R&D · pretraining · alignment"),
    "Applied AI":                           ("Applied AI",    "Customer deployments · prompt eng · solutions"),
    "Compute":                              ("Compute",       "Accelerators · clusters · supply chain"),
    "Engineering & Design - Product":       ("Product Eng",   "Public API · Console · platform · design eng"),
    "Security":                             ("Security",      "Product sec · infra sec · model security"),
    "Software Engineering - Infrastructure":("Infra",         "Reliability · platform · observability"),
    "Technical Program Management":         ("TPM",           "Technical program · cross-team coordination"),
}

# Stable palette for seniority donut (matches the original template aesthetic).
SENIORITY_PALETTE = [
    ("Staff",       "#1C1A17"),
    ("Principal",   "#2A2723"),
    ("Director",    "#3B3833"),
    ("VP",          "#4F4B43"),
    ("Manager",     "oklch(0.55 0.10 50)"),
    ("Lead",        "oklch(0.62 0.12 45)"),
    ("Senior",      "oklch(0.70 0.10 55)"),
    ("Mid",         "oklch(0.78 0.07 60)"),
    ("Entry",       "oklch(0.85 0.05 65)"),
    ("Intern",      "oklch(0.88 0.03 70)"),
    ("Unspecified", "#D9D2C2"),
]


def _short_subtitle(title: str) -> str:
    """Tiny subtitle for the table: a few words after the comma in the title."""
    if "," in title:
        return title.split(",", 1)[1].strip()
    return ""


def _is_remote(loc: str, loc_type: str | None) -> bool:
    if loc_type and "remote" in loc_type.lower():
        return True
    if loc and "remote" in loc.lower():
        return True
    return False


def _salary_label(lo: int | None, hi: int | None) -> str:
    if lo and hi:
        return f"${lo//1000}K – ${hi//1000}K"
    return "—"


def _top_techs_for_jobs(jobs: list[dict], n: int = 6) -> list[dict]:
    c: Counter[str] = Counter()
    for j in jobs:
        c.update(j.get("technologies", []))
    return [{"name": t, "count": k} for t, k in c.most_common(n)]


def _roi_by_tech(jobs: list[dict], min_n: int = 4, top_n: int = 12) -> list[dict]:
    """Average mid-range salary among jobs mentioning each tech."""
    bucket: dict[str, list[int]] = defaultdict(list)
    for j in jobs:
        s = j.get("salary_mid_usd")
        if not s:
            continue
        for tech in j.get("technologies", []):
            bucket[tech].append(s)
    rows = []
    for tech, salaries in bucket.items():
        if len(salaries) < min_n:
            continue
        rows.append({
            "tech": tech,
            "avg_salary": sum(salaries) / len(salaries),
            "n": len(salaries),
        })
    rows.sort(key=lambda r: r["avg_salary"], reverse=True)
    return rows[:top_n]


def _salary_by_dept(jobs: list[dict]) -> list[dict]:
    bucket: dict[str, list[dict]] = defaultdict(list)
    for j in jobs:
        if j.get("salary_mid_usd"):
            bucket[j["primary_department"]].append(j)
    rows = []
    for dept, items in bucket.items():
        mids = [x["salary_mid_usd"] for x in items]
        rows.append({
            "dept": DEPT_META.get(dept, (dept, ""))[0],
            "count": len(items),
            "min": min(x["salary_min_usd"] for x in items),
            "max": max(x["salary_max_usd"] for x in items),
            "avg": sum(mids) / len(mids),
            "median": median(mids),
        })
    rows.sort(key=lambda r: r["avg"], reverse=True)
    return rows


def _seniority_series(jobs: list[dict]) -> list[dict]:
    counts = Counter(j["seniority"] for j in jobs)
    series = []
    for label, color in SENIORITY_PALETTE:
        if counts.get(label, 0) > 0:
            series.append({"label": label, "count": counts[label], "color": color})
    return series


def _job_payload(j: dict) -> dict:
    dept = j["primary_department"]
    short = DEPT_META.get(dept, (dept, ""))[0]
    loc = j.get("location", "") or ""
    return {
        "title": j["title"],
        "subtitle": _short_subtitle(j["title"]),
        "url": j["url"],
        "dept": dept,
        "dept_short": short,
        "seniority": j["seniority"],
        "stack": j.get("technologies", []),
        "location": loc.split(";")[0].strip() or "—",
        "is_remote": _is_remote(loc, j.get("location_type")),
        "salary_label": _salary_label(j.get("salary_min_usd"), j.get("salary_max_usd")),
        "salary_mid": j.get("salary_mid_usd"),
    }


def build_payload(jobs: list[dict], total_pool: int) -> dict:
    now = datetime.now(timezone.utc)

    # Departments — sorted by count desc, with localized short labels.
    dept_counts = Counter(j["primary_department"] for j in jobs)
    depts = []
    for dept, count in dept_counts.most_common():
        short, subtitle = DEPT_META.get(dept, (dept, ""))
        depts.append({"name": dept, "short": short, "subtitle": subtitle, "count": count})

    # Tech per department (top 6 each).
    by_dept: dict[str, list[dict]] = defaultdict(list)
    for j in jobs:
        by_dept[j["primary_department"]].append(j)
    tech_by_dept = []
    for d in depts:
        tech_by_dept.append({
            "dept": d["short"],
            "subtitle": f"{d['count']} postings",
            "items": _top_techs_for_jobs(by_dept[d["name"]], n=6),
        })

    # Salary stats.
    sal_jobs = [j for j in jobs if j.get("salary_mid_usd")]
    salary_mids = [j["salary_mid_usd"] for j in sal_jobs]
    unique_techs = len({t for j in jobs for t in j.get("technologies", [])})

    return {
        "meta": {
            "snapshot_iso":   now.strftime("%Y-%m-%d · %H:%M UTC"),
            "snapshot_date":  now.strftime("%Y-%m-%d"),
            "run_id":         now.strftime("%y%m%d%H%M"),
            "total_jobs":     len(jobs),
            "total_pool":     total_pool,
            "with_salary":    len(sal_jobs),
            "salary_avg":     sum(salary_mids)/len(salary_mids) if salary_mids else None,
            "salary_median":  median(salary_mids) if salary_mids else None,
            "salary_min":     min(j["salary_min_usd"] for j in sal_jobs) if sal_jobs else None,
            "salary_max":     max(j["salary_max_usd"] for j in sal_jobs) if sal_jobs else None,
            "unique_techs":   unique_techs,
        },
        "depts":           depts,
        "seniority":       _seniority_series(jobs),
        "tech_by_dept":    tech_by_dept,
        "roi":             _roi_by_tech(jobs),
        "salary_by_dept":  _salary_by_dept(jobs),
        "jobs":            [_job_payload(j) for j in jobs],
    }


def render(jobs: list[dict], total_pool: int, template_path: Path,
           output_path: Path) -> None:
    payload = build_payload(jobs, total_pool)
    template = template_path.read_text()
    data_json = json.dumps(payload, ensure_ascii=False)
    # Escape </script> inside JSON to keep the inline script safe.
    data_json = data_json.replace("</", "<\\/")
    html = template.replace("__DATA_JSON__", data_json)
    html = html.replace("__SNAPSHOT_DATE__", payload["meta"]["snapshot_date"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    js_src = template_path.with_name("dashboard.js")
    if js_src.exists():
        shutil.copyfile(js_src, output_path.with_name("dashboard.js"))

    print(f"  Dashboard -> {output_path}")
