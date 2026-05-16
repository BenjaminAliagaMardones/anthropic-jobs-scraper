"""Aggregate stats over normalized job records."""
from __future__ import annotations

from collections import Counter

import pandas as pd


def to_dataframe(jobs: list[dict]) -> pd.DataFrame:
    rows = []
    for j in jobs:
        rows.append({
            "id": j["id"],
            "title": j["title"],
            "department": j["primary_department"],
            "location": j["location"],
            "location_type": j.get("location_type"),
            "seniority": j["seniority"],
            "salary_min": j.get("salary_min_usd"),
            "salary_max": j.get("salary_max_usd"),
            "salary_mid": j.get("salary_mid_usd"),
            "n_technologies": len(j.get("technologies", [])),
            "technologies": ", ".join(j.get("technologies", [])),
            "url": j["url"],
        })
    return pd.DataFrame(rows)


def top_technologies(jobs: list[dict], n: int = 15) -> list[tuple[str, int]]:
    c: Counter[str] = Counter()
    for j in jobs:
        c.update(j.get("technologies", []))
    return c.most_common(n)


def salary_by_department(df: pd.DataFrame) -> pd.DataFrame:
    s = df.dropna(subset=["salary_mid"])
    if s.empty:
        return pd.DataFrame(columns=["department", "avg_mid", "median_mid", "count"])
    g = s.groupby("department")["salary_mid"].agg(["mean", "median", "count"])
    g = g.reset_index().rename(
        columns={"mean": "avg_mid", "median": "median_mid"}
    )
    return g.sort_values("avg_mid", ascending=False)


def seniority_distribution(df: pd.DataFrame) -> pd.Series:
    return df["seniority"].value_counts()


def location_distribution(df: pd.DataFrame) -> pd.Series:
    # Split joint locations like "NY; SF" into individual entries.
    expanded = []
    for loc in df["location"].dropna():
        parts = [p.strip() for p in loc.replace("|", ";").split(";") if p.strip()]
        expanded.extend(parts)
    return pd.Series(expanded).value_counts()


def department_distribution(df: pd.DataFrame) -> pd.Series:
    return df["department"].value_counts()


def summary(jobs: list[dict], df: pd.DataFrame) -> dict:
    sal = df.dropna(subset=["salary_mid"])
    return {
        "total_jobs": len(df),
        "jobs_with_salary": len(sal),
        "salary_overall_avg": float(sal["salary_mid"].mean()) if len(sal) else None,
        "salary_overall_median": float(sal["salary_mid"].median()) if len(sal) else None,
        "salary_overall_min": float(sal["salary_min"].min()) if len(sal) else None,
        "salary_overall_max": float(sal["salary_max"].max()) if len(sal) else None,
        "top_techs": top_technologies(jobs, 15),
        "salary_by_dept": salary_by_department(df),
        "seniority": seniority_distribution(df),
        "locations": location_distribution(df).head(15),
        "departments": department_distribution(df),
    }
