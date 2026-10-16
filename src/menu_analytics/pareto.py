"""ABC (Pareto) analysis: which few items carry most of the value."""

from __future__ import annotations

import pandas as pd


def abc_analysis(
    items: pd.DataFrame, value: str = "total_cm", a: float = 0.80, b: float = 0.95
) -> pd.DataFrame:
    """Rank items by `value` and tag them A (first `a` of cumulative value), B, or C."""
    df = items.sort_values(value, ascending=False).reset_index(drop=True).copy()
    total = df[value].clip(lower=0).sum()
    df["cum_share"] = df[value].clip(lower=0).cumsum() / total
    df["item_share"] = (df.index + 1) / len(df)
    prev = df["cum_share"].shift(fill_value=0.0)
    df["abc"] = "C"
    df.loc[prev < b, "abc"] = "B"
    df.loc[prev < a, "abc"] = "A"
    return df
