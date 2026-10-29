"""Draw the ERD of the MySQL schema to database/sql/erd.png.

Usage:
    python database/draw_erd.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.plotting import SERIES, TEXT_PRIMARY, TEXT_SECONDARY, SURFACE  # noqa: E402

HEADER = SERIES[0]
ROW_H = 0.42
WIDTH = 4.6

TABLES = {
    "holidays": (0.3, 7.2, [
        ("PK", "holiday_id", "SMALLINT"),
        ("UQ", "holiday_date", "DATE"),
        ("", "holiday_name", "VARCHAR(64)"),
    ]),
    "traffic_observations": (6.6, 9.0, [
        ("PK", "observation_id", "INT UNSIGNED"),
        ("UQ", "date_time", "DATETIME"),
        ("", "traffic_volume", "INT UNSIGNED"),
        ("", "temp", "DECIMAL(6,2)  K"),
        ("", "rain_1h", "DECIMAL(7,2)  mm"),
        ("", "snow_1h", "DECIMAL(5,2)  mm"),
        ("", "clouds_all", "TINYINT  %"),
        ("FK", "holiday_id", "SMALLINT"),
        ("", "created_at", "TIMESTAMP"),
        ("", "updated_at", "TIMESTAMP"),
    ]),
    "observation_weather": (12.9, 7.2, [
        ("PK FK", "observation_id", "INT UNSIGNED"),
        ("PK FK", "condition_id", "SMALLINT"),
        ("", "condition_rank", "TINYINT"),
    ]),
    "weather_conditions": (19.2, 7.2, [
        ("PK", "condition_id", "SMALLINT"),
        ("UQ", "weather_main", "VARCHAR(32)"),
        ("UQ", "weather_description", "VARCHAR(64)"),
    ]),
}


def draw_table(ax, name, x, y_top, cols):
    h = ROW_H * (len(cols) + 1)
    ax.add_patch(FancyBboxPatch((x, y_top - h), WIDTH, h, boxstyle="round,pad=0,rounding_size=0.08",
                                facecolor="white", edgecolor="#c9c8c3", linewidth=1.2))
    ax.add_patch(FancyBboxPatch((x, y_top - ROW_H), WIDTH, ROW_H, boxstyle="round,pad=0,rounding_size=0.08",
                                facecolor=HEADER, edgecolor=HEADER))
    ax.text(x + WIDTH / 2, y_top - ROW_H / 2, name, ha="center", va="center", color="white",
            fontsize=10.5, fontweight="bold")
    rows = {}
    for i, (key, col, typ) in enumerate(cols):
        cy = y_top - ROW_H * (i + 1.5)
        if i % 2:
            ax.add_patch(plt.Rectangle((x, cy - ROW_H / 2), WIDTH, ROW_H, facecolor="#f4f3f0", edgecolor="none"))
        ax.text(x + 0.12, cy, key, ha="left", va="center", fontsize=7.5, color=SERIES[1], fontweight="bold")
        ax.text(x + 0.85, cy, col, ha="left", va="center", fontsize=9,
                color=TEXT_PRIMARY, fontweight="bold" if "PK" in key else "normal")
        ax.text(x + WIDTH - 0.1, cy, typ, ha="right", va="center", fontsize=7.5, color=TEXT_SECONDARY)
        rows[col] = cy
    return rows


def crow(ax, x, y, direction, many):
    """Crow's-foot end marker. direction=+1 means the line continues to the right."""
    d = direction
    ax.plot([x, x + 0.22 * d], [y, y], color=TEXT_SECONDARY, lw=1.2)
    if many:
        for dy in (-0.15, 0, 0.15):
            ax.plot([x, x + 0.3 * d], [y + dy, y], color=TEXT_SECONDARY, lw=1.2)
        ax.plot([x + 0.38 * d] * 2, [y - 0.14, y + 0.14], color=TEXT_SECONDARY, lw=1.2)   # optional/one bar
    else:
        for off in (0.18, 0.3):
            ax.plot([x + off * d] * 2, [y - 0.14, y + 0.14], color=TEXT_SECONDARY, lw=1.2)


def link(ax, x1, y1, x2, y2, many_left, many_right, label):
    xm = (x1 + x2) / 2
    ax.plot([x1, xm, xm, x2], [y1, y1, y2, y2], color=TEXT_SECONDARY, lw=1.2)
    crow(ax, x1, y1, +1, many_left)
    crow(ax, x2, y2, -1, many_right)
    ax.text(xm + 0.1, (y1 + y2) / 2, label, fontsize=8, color=TEXT_SECONDARY, ha="left", va="center", style="italic")


def main():
    fig, ax = plt.subplots(figsize=(17, 6.3))
    fig.patch.set_facecolor(SURFACE)
    ax.set_xlim(0, 24.0); ax.set_ylim(3.6, 9.9); ax.axis("off")
    pos = {name: draw_table(ax, name, x, y, cols) for name, (x, y, cols) in TABLES.items()}
    X = {n: v[0] for n, v in TABLES.items()}

    # holidays 1 --- N traffic_observations
    link(ax, X["holidays"] + WIDTH, pos["holidays"]["holiday_id"],
         X["traffic_observations"], pos["traffic_observations"]["holiday_id"],
         many_left=False, many_right=True, label="1 : N (optional)".replace(" (", "\n("))
    # traffic_observations 1 --- N observation_weather
    link(ax, X["traffic_observations"] + WIDTH, pos["traffic_observations"]["observation_id"],
         X["observation_weather"], pos["observation_weather"]["observation_id"],
         many_left=False, many_right=True, label="1 : N")
    # weather_conditions 1 --- N observation_weather
    link(ax, X["observation_weather"] + WIDTH, pos["observation_weather"]["condition_id"],
         X["weather_conditions"], pos["weather_conditions"]["condition_id"],
         many_left=True, many_right=False, label="N : 1")

    ax.text(0.3, 9.7, "ERD - metro_traffic (MySQL 8)", fontsize=14, fontweight="bold", color=TEXT_PRIMARY)
    ax.text(0.3, 4.0, "PK primary key   FK foreign key   UQ unique.   Crow's foot = many, double bar = exactly one.\n"
            "observation_weather resolves the many-to-many between hours and weather conditions "
            "(one hour can report e.g. Rain + Mist).", fontsize=8.5, color=TEXT_SECONDARY, va="top")
    out = ROOT / "database" / "sql" / "erd.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    print("ERD saved to", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
