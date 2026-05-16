"""Pipeline orchestrator: scrape -> extract tech -> analyze -> visualize."""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from src import analyzer, dashboard, scraper, skill_extractor, tech_extractor, visualize

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
TEMPLATE = ROOT / "templates" / "dashboard.html"

RAW_JSON = DATA_DIR / "jobs_raw.json"
JOBS_CSV = DATA_DIR / "jobs.csv"
TECH_CACHE = DATA_DIR / "tech_cache.json"
DASHBOARD_HTML = ROOT / "output" / "dashboard.html"


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

    print("\nTop ubicaciones:")
    for loc, count in s["locations"].items():
        print(f"  {loc:<40} {count}")

    print("\nOfertas por departamento:")
    for dept, count in s["departments"].items():
        print(f"  {dept:<42} {count}")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip Gemini, use regex-only tech extraction.")
    parser.add_argument("--reuse", action="store_true",
                        help="Reuse data/jobs_raw.json if present (no re-scrape).")
    args = parser.parse_args()

    load_dotenv()
    DATA_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)

    if args.reuse and RAW_JSON.exists():
        print(f"Reusing existing {RAW_JSON}")
        jobs = scraper.load(RAW_JSON)
    else:
        jobs = scraper.scrape(RAW_JSON)

    print(f"\nExtracting technologies (LLM={not args.no_llm})...")
    jobs = tech_extractor.extract_all(jobs, use_llm=not args.no_llm, cache_path=TECH_CACHE)

    print("Extracting skills (regex)...")
    jobs = skill_extractor.annotate(jobs)

    # Re-save raw with technologies attached.
    import json
    RAW_JSON.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    df = analyzer.to_dataframe(jobs)
    df.drop(columns=["technologies"]).to_csv(JOBS_CSV, index=False)
    # Save full version with techs too
    df.to_csv(DATA_DIR / "jobs_with_techs.csv", index=False)
    print(f"Saved {JOBS_CSV}")

    stats = analyzer.summary(jobs, df)

    print("\nGenerating charts...")
    visualize.plot_top_techs(stats["top_techs"], OUT_DIR / "top_technologies.png")
    visualize.plot_salary_by_dept(stats["salary_by_dept"], OUT_DIR / "salary_by_department.png")
    visualize.plot_seniority(stats["seniority"], OUT_DIR / "seniority_distribution.png")
    visualize.plot_department_distribution(stats["departments"], OUT_DIR / "departments.png")
    visualize.plot_locations_map(stats["locations"], OUT_DIR / "locations_map.html")
    print(f"  -> {OUT_DIR}/*.png and locations_map.html")

    print("\nRendering HTML dashboard...")
    # total_pool is best-effort: read it back from the raw API if available.
    total_pool = len(jobs)
    try:
        import requests as _rq
        r = _rq.get(scraper.GREENHOUSE_URL, timeout=15)
        if r.ok:
            total_pool = len(r.json().get("jobs", [])) or total_pool
    except Exception:
        pass
    mode = "regex" if args.no_llm else "gemini+regex"
    dashboard.render(jobs, total_pool, TEMPLATE, DASHBOARD_HTML, mode)

    print_summary(stats)
    print(f"\nDashboard listo: open {DASHBOARD_HTML}")


if __name__ == "__main__":
    main()
