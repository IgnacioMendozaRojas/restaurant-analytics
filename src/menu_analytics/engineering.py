"""Menu engineering (Kasavana & Smith, 1982).

Each dish is placed on two axes, always *within its own menu section*:

- Popularity: menu-mix share against a threshold of 70% of an equal share,
  i.e. 0.7 / N for a section with N dishes.
- Profitability: unit contribution margin (net price - food cost) against the
  section's sales-weighted average contribution margin.

    high popularity, high margin  -> Star        keep, protect, feature
    high popularity, low margin   -> Plowhorse   re-engineer cost or nudge price
    low popularity,  high margin  -> Puzzle      reposition, promote, rename
    low popularity,  low margin   -> Dog         remove or rethink

Contribution margin uses *net* revenue (after discounts), which is what the
restaurant actually keeps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

POPULARITY_FACTOR = 0.70

ACTIONS = {
    "Star": "Keep and protect: best placement, consistent portioning",
    "Plowhorse": "Re-engineer: trim recipe cost or test a small price increase",
    "Puzzle": "Reposition: better menu placement, rename, suggestive selling",
    "Dog": "Remove or redesign",
}


def menu_engineering(
    sales: pd.DataFrame,
    section: str = "division",
    min_qty: int = 1,
    exclude_sections: tuple[str, ...] = ("Envase", "Salsa Pote Negro"),
) -> pd.DataFrame:
    """Aggregate product sales and compute unit economics per dish.

    `sales` needs product, qty, gross_sales, discounts, food_cost and the section column.
    """
    df = sales[~sales[section].isin(exclude_sections)]
    g = (
        df.groupby([section, "product"], as_index=False)[
            ["qty", "gross_sales", "discounts", "food_cost"]
        ]
        .sum()
        .query("qty >= @min_qty")
    )
    g["net_sales"] = g["gross_sales"] - g["discounts"]
    g = g[g["net_sales"] > 0].copy()
    g["unit_price"] = g["net_sales"] / g["qty"]
    g["unit_cost"] = g["food_cost"] / g["qty"]
    g["unit_cm"] = g["unit_price"] - g["unit_cost"]
    g["total_cm"] = g["unit_cm"] * g["qty"]
    g["food_cost_pct"] = g["food_cost"] / g["net_sales"]
    return classify_menu(g, section)


def classify_menu(items: pd.DataFrame, section: str = "division") -> pd.DataFrame:
    out = []
    for _, grp in items.groupby(section):
        grp = grp.copy()
        n = len(grp)
        grp["mix_pct"] = grp["qty"] / grp["qty"].sum()
        grp["popularity_threshold"] = POPULARITY_FACTOR / n
        grp["cm_threshold"] = grp["total_cm"].sum() / grp["qty"].sum()
        popular = grp["mix_pct"] >= grp["popularity_threshold"]
        profitable = grp["unit_cm"] >= grp["cm_threshold"]
        grp["class"] = np.select(
            [popular & profitable, popular & ~profitable, ~popular & profitable],
            ["Star", "Plowhorse", "Puzzle"],
            default="Dog",
        )
        out.append(grp)
    res = pd.concat(out, ignore_index=True)
    res["action"] = res["class"].map(ACTIONS)
    return res.sort_values([section, "total_cm"], ascending=[True, False]).reset_index(drop=True)


def section_summary(classified: pd.DataFrame, section: str = "division") -> pd.DataFrame:
    """Contribution and class mix per menu section."""
    s = classified.groupby(section).agg(
        dishes=("product", "count"),
        qty=("qty", "sum"),
        net_sales=("net_sales", "sum"),
        food_cost=("food_cost", "sum"),
        total_cm=("total_cm", "sum"),
    )
    s["food_cost_pct"] = s["food_cost"] / s["net_sales"]
    s["cm_share"] = s["total_cm"] / s["total_cm"].sum()
    counts = classified.pivot_table(
        index=section, columns="class", values="product", aggfunc="count", fill_value=0
    )
    return s.join(counts).sort_values("total_cm", ascending=False)
