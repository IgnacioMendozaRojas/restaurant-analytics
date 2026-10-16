"""Monthly break-even and margin of safety.

    contribution margin ratio  CMR = 1 - food cost % - card fee % x card share of sales
    break-even sales           BE  = fixed costs / CMR
    margin of safety               = (sales - BE) / sales

Everything is per month and before taxes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BreakEven:
    sales: float
    fixed_costs: float
    food_cost_pct: float
    card_fee_pct: float
    card_share: float

    @property
    def cm_ratio(self) -> float:
        return 1.0 - self.food_cost_pct - self.card_fee_pct * self.card_share

    @property
    def break_even_sales(self) -> float:
        if self.cm_ratio <= 0:
            return float("inf")
        return self.fixed_costs / self.cm_ratio

    @property
    def operating_profit(self) -> float:
        return self.sales * self.cm_ratio - self.fixed_costs

    @property
    def margin_of_safety(self) -> float:
        return (self.sales - self.break_even_sales) / self.sales

    def with_food_cost(self, pct: float) -> BreakEven:
        return BreakEven(self.sales, self.fixed_costs, pct, self.card_fee_pct, self.card_share)


def break_even(
    sales: float,
    fixed_costs: float,
    food_cost_pct: float,
    card_fee_pct: float = 0.0,
    card_share: float = 0.0,
) -> BreakEven:
    for name, v in [
        ("food_cost_pct", food_cost_pct),
        ("card_fee_pct", card_fee_pct),
        ("card_share", card_share),
    ]:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{name} must be a fraction between 0 and 1, got {v}")
    return BreakEven(sales, fixed_costs, food_cost_pct, card_fee_pct, card_share)
