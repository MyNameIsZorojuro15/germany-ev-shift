"""Static figures for the README (matplotlib) and a one-page interactive dashboard (docs/index.html, Plotly)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT, FIG = ROOT / "outputs", ROOT / "reports" / "figures"
BLUE, GREY, ORANGE = "#1f5fa8", "#9aa3ad", "#d9822b"


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((OUT / "results.json").read_text())
    m = pd.read_csv(OUT / "bmw_group_month.csv")
    groups = pd.DataFrame(res["groups_ytd"]).query("grp != 'Other'").sort_values("bev_index")
    swing = pd.DataFrame(res["swing"]).query("grp != 'Other'").sort_values("bev_market_share_change_pp")

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(m.month, m.market_bev_share, color=GREY, lw=2, label="Germany, all brands")
    ax.plot(m.month, m.bmw_group_bev_share, color=BLUE, lw=2, label="BMW Group (BMW, MINI, Rolls-Royce)")
    ax.set_ylabel("Battery-electric share of new cars, %")
    ax.set_xticks(m.month[::3]); ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "bev_share_bmw_vs_market.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh(groups.grp, groups.bev_index, color=[BLUE if g == "BMW Group" else GREY for g in groups.grp])
    ax.axvline(1, color="black", lw=1); ax.set_xlabel("BEV index: share of electric market / share of total market (1 = average)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "bev_index_by_group.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh(swing.grp, swing.bev_market_share_change_pp, color=[BLUE if g == "BMW Group" else (ORANGE if v > 0 else GREY) for g, v in zip(swing.grp, swing.bev_market_share_change_pp)])
    ax.axvline(0, color="black", lw=1); ax.set_xlabel("Change in share of the electric-car market, percentage points (YTD vs a year earlier)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "bev_share_swing.png", dpi=150); plt.close(fig)

    dash = make_subplots(rows=3, cols=1, vertical_spacing=0.12, subplot_titles=(
        "Battery-electric share of new cars: BMW Group vs Germany", "BEV index by group, " + res["ytd_window"],
        "Who gained share of the electric market, " + res["ytd_window"]))
    dash.add_trace(go.Scatter(x=m.month, y=m.market_bev_share, name="Germany", line=dict(color=GREY)), 1, 1)
    dash.add_trace(go.Scatter(x=m.month, y=m.bmw_group_bev_share, name="BMW Group", line=dict(color=BLUE)), 1, 1)
    dash.add_trace(go.Bar(y=groups.grp, x=groups.bev_index, orientation="h", marker_color=[BLUE if g == "BMW Group" else GREY for g in groups.grp], showlegend=False), 2, 1)
    dash.add_trace(go.Bar(y=swing.grp, x=swing.bev_market_share_change_pp, orientation="h", marker_color=[BLUE if g == "BMW Group" else GREY for g in swing.grp], showlegend=False), 3, 1)
    dash.update_layout(height=1100, title="Germany's shift to electric cars: where BMW Group stands", template="simple_white",
                       margin=dict(l=140, r=30, t=90, b=40))
    dash.add_annotation(text="Source: Kraftfahrt-Bundesamt (KBA), FZ 8, Datenlizenz Deutschland 2.0. Analysis: Daniel Freire.",
                        xref="paper", yref="paper", x=0, y=-0.05, showarrow=False, font=dict(size=10))
    (ROOT / "docs").mkdir(exist_ok=True)
    dash.write_html(ROOT / "docs" / "index.html", include_plotlyjs="cdn", full_html=True)
    print("figures and dashboard written")


if __name__ == "__main__":
    main()
