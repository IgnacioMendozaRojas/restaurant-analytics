"""Theoretical ingredient usage from sales, adjusted for yield (merma).

A recipe lists the *net* quantity that ends up on the plate. Many ingredients lose
weight before that: avocado is peeled and pitted, potatoes are peeled, meat shrinks.
With a yield of y%, the gross quantity that has to be bought is

    gross = net / (y / 100)

Summing gross quantities over everything sold gives the theoretical purchases for a
period. Comparing it with real purchases is the classic way to find waste, over-
portioning or theft.
"""

from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd

# Convert recipe units to the unit the ingredient is bought and costed in
TO_BASE = {"g": ("Kilo", 1e-3), "kg": ("Kilo", 1.0), "mL": ("Litro", 1e-3), "L": ("Litro", 1.0)}


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(" - ", " ").replace("-", " ").split())


def ingredient_usage(
    quantities: pd.DataFrame,
    recipes: pd.DataFrame,
    costs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Gross and net ingredient requirements for the products sold.

    quantities: product_id, qty (any extra columns such as date are summed over)
    recipes:    product_id, ingredient, qty, unit, yield_pct
    costs:      ingredient, unit_cost (per Kilo / Litro / unit)
    """
    sold = quantities.groupby("product_id", as_index=False)["qty"].sum()
    m = recipes.merge(sold, on="product_id", suffixes=("_recipe", "_sold"))
    y = m["yield_pct"].fillna(100.0).clip(lower=1.0) / 100.0
    factor = m["unit"].map(lambda u: TO_BASE.get(u, (u, 1.0))[1])
    m["base_unit"] = m["unit"].map(lambda u: TO_BASE.get(u, (u, 1.0))[0])
    m["net_qty"] = m["qty_recipe"] * m["qty_sold"] * factor
    m["gross_qty"] = m["net_qty"] / y
    m["waste_qty"] = m["gross_qty"] - m["net_qty"]

    usage = m.groupby(["ingredient", "base_unit"], as_index=False)[
        ["net_qty", "gross_qty", "waste_qty"]
    ].sum()
    usage["yield_pct"] = np.where(
        usage["gross_qty"] > 0, usage["net_qty"] / usage["gross_qty"] * 100, 100.0
    )

    if costs is not None:
        price = costs.assign(key=costs["ingredient"].map(_key)).drop_duplicates("key")
        usage["key"] = usage["ingredient"].map(_key)
        usage = usage.merge(price[["key", "unit_cost"]], on="key", how="left").drop(columns="key")
        usage["gross_cost"] = usage["gross_qty"] * usage["unit_cost"]
        usage["waste_cost"] = usage["waste_qty"] * usage["unit_cost"]
    return usage.sort_values("gross_qty", ascending=False).reset_index(drop=True)
