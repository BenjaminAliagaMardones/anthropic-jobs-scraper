"""Pipeline orchestrator: scrape -> analyze -> render dashboard."""
from __future__ import annotations

from pathlib import Path

from src import analyzer, dashboard, scraper

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
TEMPLATE = ROOT / "templates" / "dashboard.html"

RAW_JSON = DATA_DIR / "jobs_raw.json"
JOBS_CSV = DATA_DIR / "jobs.csv"
DASHBOARD_HTML = OUT_DIR / "dashboard.html"


def fmt_usd(v: float | None) -> str:
    return f"${v:,.0f}" if v else "n/a"


def print_summary(s: dict) -> None:
    print("\n" + "=" * 72)
    print("RESUMEN — Ofertas de Engineering en Anthropic")
    print("=" * 72)
    print(f"Total de ofertas analizadas: {s['total_jobs']}")
    print(f"Ofertas con salario publicado: {s['jobs_with_salary']}")
    if s["salary_overall_avg"]:
        print(
            f"Salario (mid-range) — avg: {fmt_usd(s['salary_overall_avg'])} | "
            f"median: {fmt_usd(s['salary_overall_median'])} | "
            f"rango: {fmt_usd(s['salary_overall_min'])} – {fmt_usd(s['salary_overall_max'])}"
        )

    print("\nTop 15 tecnologías:")
    for tech, count in s["top_techs"]:
        bar = "█" * min(count, 40)
        print(f"  {tech:<22} {count:>3}  {bar}")

    print("\nSalario promedio por departamento:")
    for _, row in s["salary_by_dept"].iterrows():
        print(
            f"  {row['department']:<42} "
            f"avg={fmt_usd(row['avg_mid'])}  median={fmt_usd(row['median_mid'])}  "
            f"(n={int(row['count'])})"
        )

    print("\nDistribución por seniority:")
    total = int(s["seniority"].sum())
    for label, count in s["seniority"].items():
        pct = 100 * count / total if total else 0
        print(f"  {label:<14} {count:>3}  ({pct:5.1f}%)")

    print("\nOfertas por departamento:")
    for dept, count in s["departments"].items():
        print(f"  {dept:<42} {count}")
    print("=" * 72)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)

    jobs = scraper.scrape(RAW_JSON)

    df = analyzer.to_dataframe(jobs)
    df.drop(columns=["technologies"]).to_csv(JOBS_CSV, index=False)
    print(f"Saved {JOBS_CSV}")

    stats = analyzer.summary(jobs, df)

    print("\nRendering HTML dashboard...")
    total_pool = len(jobs)
    try:
        import requests as _rq
        r = _rq.get(scraper.GREENHOUSE_URL, timeout=15)
        if r.ok:
            total_pool = len(r.json().get("jobs", [])) or total_pool
    except Exception:
        pass
    dashboard.render(jobs, total_pool, TEMPLATE, DASHBOARD_HTML)

    print_summary(stats)
    print(f"\nDashboard listo: open {DASHBOARD_HTML}")


if __name__ == "__main__":
    main()
