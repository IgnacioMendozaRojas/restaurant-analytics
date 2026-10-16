"""Loaders for the datasets in data/.

All money is in Chilean pesos (CLP). Volumes and totals are scaled by a constant
factor to protect the size of the business; prices, unit costs, recipe quantities,
yields and every ratio are real.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass
class Datasets:
    monthly_sales: pd.DataFrame
    daily_qty: pd.DataFrame
    recipes: pd.DataFrame
    ingredient_costs: pd.DataFrame
    payment_mix: pd.DataFrame
    fixed_costs: pd.DataFrame
    cash_month: pd.DataFrame


def load(data_dir: Path | str = DATA_DIR) -> Datasets:
    d = Path(data_dir)
    read = lambda name, **kw: pd.read_csv(d / name, **kw)  # noqa: E731
    return Datasets(
        monthly_sales=read("monthly_product_sales.csv", dtype={"product_id": str}),
        daily_qty=read("daily_product_qty.csv", dtype={"product_id": str}, parse_dates=["date"]),
        recipes=read("recipes.csv", dtype={"product_id": str, "ingredient_id": str}),
        ingredient_costs=read("ingredient_costs.csv"),
        payment_mix=read("payment_mix.csv"),
        fixed_costs=read("fixed_costs.csv"),
        cash_month=read("cash_month_2023_03.csv"),
    )
