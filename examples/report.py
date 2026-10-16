"""Build the analysis behind the README: tables in docs/results.md and figures in docs/.

python examples/report.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from menu_analytics import abc_analysis, break_even, ingredient_usage, load, menu_engineering
from menu_analytics.engineering import section_summary

DOCS = Path(__file__).resolve().parents[1] / "docs"
Q3 = ["2023-07", "2023-08", "2023-09"]
CARD_FEE = 0.0168  # fees / card sales observed in March 2023

THEMES = {
    "light": dict(
        surface="#fcfcfb",
        text="#0b0b0b",
        muted="#52514e",
        grid="#e4e3df",
        series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
    ),
    "dark": dict(
        surface="#1a1a19",
        text="#f0efec",
        muted="#c3c2b7",
        grid="#34332f",
        series=["#3987e5", "#d95926", "#199e70", "#c98500"],
    ),
}
CLASS_ORDER = ["Star", "Plowhorse", "Puzzle", "Dog"]


def priced_costs(d) -> pd.DataFrame:
    """Ingredient prices, plus resale items (drinks, packaging) priced from POS unit cost."""
    sold = d.monthly_sales.groupby("product")[["food_cost", "qty"]].sum()
    resale = (sold["food_cost"] / sold["qty"]).rename("unit_cost").reset_index()
    resale = resale.rename(columns={"product": "ingredient"})
    return pd.concat([d.ingredient_costs[["ingredient", "unit_cost"]], resale], ignore_index=True)


def analyse():
    d = load()
    q3 = d.monthly_sales[d.monthly_sales["month"].isin(Q3)]
    me = menu_engineering(q3)
    sections = section_summary(me)
    abc = abc_analysis(me)
    usage = ingredient_usage(d.daily_qty, d.recipes, priced_costs(d))

    months = len(Q3)
    net_sales = me["net_sales"].sum() / months
    theoretical_fc = me["food_cost"].sum() / me["net_sales"].sum()
    pm = d.payment_mix[d.payment_mix["month"].isin(Q3)]
    card_share = pm[pm["method"].str.startswith("Tarjeta")]["sales"].sum() / pm["sales"].sum()
    fixed = d.fixed_costs["monthly_amount"].sum()
    cash = d.cash_month.iloc[0]
    purchases_ratio = cash["merchandise_purchases"] / cash["net_sales"]
    be = break_even(net_sales, fixed, theoretical_fc, CARD_FEE, card_share)
    return dict(
        me=me, sections=sections, abc=abc, usage=usage, be=be, purchases_ratio=purchases_ratio, d=d
    )


def fmt_m(x: float) -> str:
    return f"{x / 1e6:,.1f}M"


def write_results(r) -> str:
    me, sections, abc, usage, be = r["me"], r["sections"], r["abc"], r["usage"], r["be"]
    lines = [
        "## Menu sections, Q3 2023 (Jul-Sep)",
        "",
        "| Section | Dishes | Net sales | Food cost % | Share of contribution | Stars | Plowhorses | Puzzles | Dogs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in sections.iterrows():
        lines.append(
            f"| {name} | {int(s.dishes)} | {fmt_m(s.net_sales)} | {s.food_cost_pct:.1%} | "
            f"{s.cm_share:.1%} | {int(s.Star)} | {int(s.Plowhorse)} | {int(s.Puzzle)} | {int(s.Dog)} |"
        )

    counts = abc.groupby("abc").agg(items=("product", "count"), cm=("total_cm", "sum"))
    a = counts.loc["A"]
    lines += [
        "",
        f"**ABC:** {int(a['items'])} of {len(abc)} dishes ({a['items'] / len(abc):.0%}) "
        f"generate {a['cm'] / abc['total_cm'].sum():.0%} of total contribution.",
    ]

    top = me.sort_values("total_cm", ascending=False).head(10)
    lines += [
        "",
        "## Top 10 dishes by contribution",
        "",
        "| Dish | Section | Units | Avg. net price | Unit cost | Food cost % | Class |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for _, t in top.iterrows():
        lines.append(
            f"| {t['product']} | {t.division} | {t.qty:,} | {t.unit_price:,.0f} | "
            f"{t.unit_cost:,.0f} | {t.food_cost_pct:.1%} | {t['class']} |"
        )

    w = usage.dropna(subset=["unit_cost"]).sort_values("waste_cost", ascending=False)
    total_waste = w["waste_cost"].sum()
    lines += [
        "",
        "## Yield loss, 17 days of sales (Jan-Feb 2023)",
        "",
        "| Ingredient | Yield | Bought (gross) | Lost to trimming | Cost of loss | Share of loss |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, x in w.head(5).iterrows():
        lines.append(
            f"| {x.ingredient} | {x.yield_pct:.0f}% | {x.gross_qty:,.1f} {x.base_unit} | "
            f"{x.waste_qty:,.1f} {x.base_unit} | {x.waste_cost:,.0f} | "
            f"{x.waste_cost / total_waste:.0%} |"
        )
    lines += [
        "",
        f"Priced ingredients cover {usage['unit_cost'].notna().mean():.0%} of recipe lines.",
    ]

    bp = be.with_food_cost(r["purchases_ratio"])
    lines += [
        "",
        "## Monthly break-even",
        "",
        "| Scenario | Food cost | Contribution ratio | Break-even sales | Margin of safety |",
        "|---|---:|---:|---:|---:|",
        f"| Theoretical (recipe costs) | {be.food_cost_pct:.1%} | {be.cm_ratio:.1%} | "
        f"{fmt_m(be.break_even_sales)} | {be.margin_of_safety:.0%} |",
        f"| Observed (purchases / sales) | {bp.food_cost_pct:.1%} | {bp.cm_ratio:.1%} | "
        f"{fmt_m(bp.break_even_sales)} | {bp.margin_of_safety:.0%} |",
        "",
        f"Average monthly net sales {fmt_m(be.sales)}, fixed costs {fmt_m(be.fixed_costs)}, "
        f"card share of sales {be.card_share:.0%}.",
    ]
    text = "\n".join(lines) + "\n"
    (DOCS / "results.md").write_text(text, encoding="utf-8")
    return text


def _fig(theme, title, subtitle, size=(9, 5)):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=size, dpi=150)
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme["grid"])
    ax.tick_params(colors=theme["muted"], labelsize=9)
    ax.set_axisbelow(True)
    fig.text(0.07, 0.95, title, color=theme["text"], fontsize=13, weight="bold")
    fig.text(0.07, 0.905, subtitle, color=theme["muted"], fontsize=9.5)
    fig.subplots_adjust(left=0.1, right=0.96, top=0.84, bottom=0.12)
    return fig, ax


def figures(r) -> None:
    import matplotlib.pyplot as plt

    me = r["me"]
    sec = me[me["division"] == "Completería"].copy()
    usage = r["usage"].dropna(subset=["unit_cost"]).sort_values("waste_cost", ascending=False)
    for mode, th in THEMES.items():
        # 1. Menu engineering matrix for one section
        fig, ax = _fig(
            th,
            "Menu engineering matrix: hot dogs (completos)",
            "Q3 2023 · each dot is a dish · dashed lines are the section thresholds",
        )
        colors = dict(zip(CLASS_ORDER, th["series"], strict=True))
        for cls in CLASS_ORDER:
            s = sec[sec["class"] == cls]
            ax.scatter(
                s["mix_pct"] * 100,
                s["unit_cm"],
                s=70,
                color=colors[cls],
                label=cls,
                edgecolor=th["surface"],
                linewidth=1.5,
                zorder=3,
            )
        ax.axvline(sec["popularity_threshold"].iloc[0] * 100, color=th["muted"], ls="--", lw=1)
        ax.axhline(sec["cm_threshold"].iloc[0], color=th["muted"], ls="--", lw=1)
        ax.set_xscale("log")
        ax.set_xlabel("Menu mix, % of section units (log scale)", color=th["muted"], fontsize=9)
        ax.set_ylabel("Unit contribution margin (CLP)", color=th["muted"], fontsize=9)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}%"))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(color=th["grid"], lw=0.8)
        top = sec.sort_values("qty", ascending=False).iloc[0]
        ax.annotate(
            top["product"],
            (top["mix_pct"] * 100, top["unit_cm"]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            color=th["text"],
            fontsize=9,
        )
        ax.legend(frameon=False, fontsize=9, labelcolor=th["text"], loc="upper left")
        fig.savefig(DOCS / f"menu_matrix_{mode}.png", facecolor=th["surface"])
        plt.close(fig)

        # 2. Yield loss by ingredient
        top = usage[usage["waste_cost"] > 0].head(5).iloc[::-1]
        fig, ax = _fig(
            th,
            "Where trimming loss costs money",
            "Cost of weight lost before plating · 17 days of sales · label = yield",
        )
        ax.barh(top["ingredient"], top["waste_cost"] / 1e3, color=th["series"][0], height=0.6)
        for y, (v, yp) in enumerate(zip(top["waste_cost"] / 1e3, top["yield_pct"], strict=True)):
            ax.annotate(
                f"{v:,.0f}k  ·  {yp:.0f}% yield",
                (v, y),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                color=th["text"],
                fontsize=9,
            )
        ax.set_xlabel("Thousand CLP", color=th["muted"], fontsize=9)
        ax.grid(axis="x", color=th["grid"], lw=0.8)
        ax.tick_params(axis="y", colors=th["text"])
        ax.set_xlim(0, top["waste_cost"].max() / 1e3 * 1.35)
        fig.subplots_adjust(left=0.22)
        fig.savefig(DOCS / f"yield_loss_{mode}.png", facecolor=th["surface"])
        plt.close(fig)

        # 3. Break-even vs food cost
        be = r["be"]
        fc = np.linspace(0.10, 0.50, 81)
        bes = [be.with_food_cost(f).break_even_sales / 1e6 for f in fc]
        fig, ax = _fig(
            th,
            "Food cost moves the break-even point",
            "Monthly break-even sales vs food cost % · fixed costs and card fees held constant",
        )
        ax.plot(fc * 100, bes, color=th["series"][0], lw=2)
        ax.axhline(be.sales / 1e6, color=th["series"][1], lw=2)
        ax.annotate(
            "Average monthly sales, Q3",
            (11, be.sales / 1e6),
            xytext=(0, 6),
            textcoords="offset points",
            color=th["text"],
            fontsize=9,
        )
        for f, label in [(be.food_cost_pct, "Recipe cost"), (r["purchases_ratio"], "Purchases")]:
            y = be.with_food_cost(f).break_even_sales / 1e6
            ax.scatter(
                [f * 100],
                [y],
                color=th["series"][2],
                s=60,
                zorder=3,
                edgecolor=th["surface"],
                linewidth=1.5,
            )
            ax.annotate(
                f"{label} {f:.0%}",
                (f * 100, y),
                xytext=(8, -14),
                textcoords="offset points",
                color=th["text"],
                fontsize=9,
            )
        ax.set_xlabel("Food cost, % of net sales", color=th["muted"], fontsize=9)
        ax.set_ylabel("Break-even sales (million CLP)", color=th["muted"], fontsize=9)
        ax.grid(axis="y", color=th["grid"], lw=0.8)
        fig.savefig(DOCS / f"break_even_{mode}.png", facecolor=th["surface"])
        plt.close(fig)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    r = analyse()
    print(write_results(r))
    figures(r)


if __name__ == "__main__":
    main()
