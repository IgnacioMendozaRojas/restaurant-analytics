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


SOURCE = (
    "Source: point-of-sale exports, recipes and purchases of the restaurant I ran in Chile in 2023. "
    "github.com/IgnacioMendozaRojas/restaurant-analytics"
)


def figures(r) -> None:
    from matplotlib.ticker import FuncFormatter

    from menu_analytics.figstyle import charts

    me = r["me"]
    sec = me[me["division"] == "Completería"].copy()
    top = sec.sort_values("qty", ascending=False).iloc[0]
    above = top["unit_cm"] >= sec["cm_threshold"].iloc[0]

    # 1. Menu engineering matrix for one section
    for c in charts(
        f"{top['product']} sells {top['mix_pct']:.0%} of hot dogs at a "
        f"{'above' if above else 'below'}-average margin",
        "Menu engineering matrix, hot dogs (completos), Q3 2023: menu mix (log scale) against "
        "unit contribution margin, CLP",
        SOURCE + " Dashed lines: section thresholds.",
    ):
        for i, cls in enumerate(CLASS_ORDER):
            s = sec[sec["class"] == cls]
            c.ax.scatter(
                s["mix_pct"] * 100,
                s["unit_cm"],
                s=50,
                color=c.color(i),
                label=cls,
                edgecolor=c.t["surface"],
                linewidth=1.2,
                zorder=3,
            )
        c.ax.axvline(sec["popularity_threshold"].iloc[0] * 100, color=c.t["muted"], ls="--", lw=0.8)
        c.ax.axhline(sec["cm_threshold"].iloc[0], color=c.t["muted"], ls="--", lw=0.8)
        c.ax.set_xscale("log")
        c.ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
        c.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        c.ax.grid(axis="x", color=c.t["grid"], linewidth=0.8)
        c.note((top["mix_pct"] * 100, top["unit_cm"]), top["product"], (-40, 25))
        c.xlabel("Menu mix, % of section units")
        c.yaxis("Unit contribution margin, CLP")
        c.legend("upper left")
        c.save(DOCS, "menu-matrix")

    # 2. Yield loss by ingredient
    usage = r["usage"].dropna(subset=["unit_cost"]).sort_values("waste_cost", ascending=False)
    lost = usage[usage["waste_cost"] > 0]
    first = lost.iloc[0]
    for c in charts(
        f"{first['ingredient']} trimming cost CLP {first['waste_cost'] / 1e3:,.0f}k in 17 days, "
        f"{first['waste_cost'] / lost['waste_cost'].sum():.0%} of all yield loss",
        "Cost of weight lost before plating, five largest ingredients, thousand CLP (yield in brackets)",
        SOURCE,
    ):
        top5 = lost.head(5)
        labels = [f"{x.ingredient} ({x.yield_pct:.0f}%)" for x in top5.itertuples()]
        c.hbars(labels, list(top5["waste_cost"] / 1e3), fmt="{:,.0f}k", highlight={labels[0]})
        c.fig.subplots_adjust(left=0.24, right=0.92, top=0.8, bottom=0.2)
        c.save(DOCS, "yield-loss")

    # 3. Break-even vs food cost
    be = r["be"]
    bp = be.with_food_cost(r["purchases_ratio"])
    fc = np.linspace(0.10, 0.50, 81)
    bes = [be.with_food_cost(f).break_even_sales / 1e6 for f in fc]
    for c in charts(
        f"A {r['purchases_ratio']:.0%} food cost lifts break-even sales "
        f"{bp.break_even_sales / be.break_even_sales - 1:.0%} above the recipe plan",
        "Monthly break-even sales against food cost, % of net sales; fixed costs and card fees held "
        "constant, million CLP",
        SOURCE,
    ):
        c.line(list(fc * 100), bes, 0, "Break-even sales")
        c.ax.axhline(be.sales / 1e6, color=c.color(1), linewidth=2)
        c.ax.annotate(
            " Q3 average sales",
            (fc[-1] * 100, be.sales / 1e6),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=c.t["text"],
            annotation_clip=False,
        )
        for f, label, off in [
            (be.food_cost_pct, "Recipe cost", (10, -18)),
            (r["purchases_ratio"], "Purchases", (-60, 18)),
        ]:
            y = be.with_food_cost(f).break_even_sales / 1e6
            c.ax.scatter([f * 100], [y], color=c.color(2), s=40, zorder=3)
            c.note((f * 100, y), f"{label} {f:.0%}: {y:.1f}M", off)
        c.ax.set_ylim(bottom=0)
        c.xlabel("Food cost, % of net sales")
        c.yaxis("Million CLP")
        c.save(DOCS, "break-even")


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    r = analyse()
    print(write_results(r))
    figures(r)


if __name__ == "__main__":
    main()
