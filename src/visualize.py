"""Chart generation: matplotlib/seaborn for static, plotly for the map."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns

sns.set_theme(style="whitegrid")

# Rough coordinates for common Anthropic office cities (lat, lon).
CITY_COORDS = {
    "San Francisco": (37.7749, -122.4194),
    "New York": (40.7128, -74.0060),
    "New York City": (40.7128, -74.0060),
    "Seattle": (47.6062, -122.3321),
    "London": (51.5074, -0.1278),
    "Dublin": (53.3498, -6.2603),
    "Zurich": (47.3769, 8.5417),
    "Tokyo": (35.6762, 139.6503),
    "Singapore": (1.3521, 103.8198),
    "Sydney": (-33.8688, 151.2093),
    "Washington": (38.9072, -77.0369),
    "Boston": (42.3601, -71.0589),
    "Toronto": (43.6532, -79.3832),
    "Remote": (0, 0),
}


def _city_from_location(loc: str) -> str | None:
    if not loc:
        return None
    head = loc.split(",")[0].strip()
    # Sometimes the location has multiple cities joined by ;
    head = head.split(";")[0].strip()
    return head or None


def plot_top_techs(top: list[tuple[str, int]], out: Path) -> None:
    if not top:
        return
    df = pd.DataFrame(top, columns=["tech", "count"]).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.barplot(data=df, y="tech", x="count", ax=ax, palette="viridis", hue="tech", legend=False)
    ax.set_title("Top 15 tecnologías más demandadas — Anthropic Engineering")
    ax.set_xlabel("Número de ofertas")
    ax.set_ylabel("")
    for i, v in enumerate(df["count"]):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_salary_by_dept(sal_df: pd.DataFrame, out: Path) -> None:
    if sal_df.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    df = sal_df.copy()
    df["avg_mid_k"] = df["avg_mid"] / 1000
    sns.barplot(data=df, x="avg_mid_k", y="department", ax=ax, palette="crest",
                hue="department", legend=False)
    ax.set_title("Salario promedio (mid-range) por departamento")
    ax.set_xlabel("USD (miles, mid-range)")
    ax.set_ylabel("")
    for i, (avg, n) in enumerate(zip(df["avg_mid_k"], df["count"])):
        ax.text(avg + 2, i, f"${avg:.0f}k (n={n})", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_seniority(series: pd.Series, out: Path) -> None:
    if series.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = sns.color_palette("Set2", len(series))
    ax.pie(series.values, labels=series.index, autopct="%1.1f%%", colors=colors,
           startangle=90, wedgeprops={"edgecolor": "white"})
    ax.set_title("Distribución de seniority")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_locations_map(loc_counts: pd.Series, out: Path) -> None:
    rows = []
    for raw_loc, count in loc_counts.items():
        city = _city_from_location(raw_loc)
        if not city:
            continue
        coords = CITY_COORDS.get(city)
        if not coords:
            # Try case-insensitive lookup
            for k, v in CITY_COORDS.items():
                if k.lower() in city.lower():
                    coords = v
                    break
        if not coords or coords == (0, 0):
            continue
        rows.append({"city": city, "lat": coords[0], "lon": coords[1], "count": int(count)})
    if not rows:
        return
    df = pd.DataFrame(rows).groupby("city", as_index=False).agg(
        {"lat": "first", "lon": "first", "count": "sum"}
    )
    fig = px.scatter_geo(
        df, lat="lat", lon="lon", size="count", text="city",
        hover_name="city", hover_data={"count": True, "lat": False, "lon": False},
        projection="natural earth",
        title="Mapa de ubicaciones — ofertas Engineering en Anthropic",
        size_max=45, color="count", color_continuous_scale="Viridis",
    )
    fig.update_traces(textposition="top center")
    fig.write_html(out)


def plot_department_distribution(series: pd.Series, out: Path) -> None:
    if series.empty:
        return
    df = series.reset_index()
    df.columns = ["department", "count"]
    df = df.sort_values("count")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=df, y="department", x="count", ax=ax, palette="rocket",
                hue="department", legend=False)
    ax.set_title("Ofertas por departamento (Engineering)")
    ax.set_xlabel("Número de ofertas")
    ax.set_ylabel("")
    for i, v in enumerate(df["count"]):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
