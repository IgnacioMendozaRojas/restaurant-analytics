import pandas as pd
import pytest

from menu_analytics import abc_analysis, break_even, ingredient_usage, load, menu_engineering


def toy_sales():
    rows = [
        # section A: 4 dishes, equal share would be 25%, threshold 17.5%
        ("A", "star", 400, 4000 * 400, 0, 1000 * 400),
        ("A", "plowhorse", 300, 2500 * 300, 0, 1000 * 300),
        ("A", "puzzle", 50, 6000 * 50, 0, 1500 * 50),
        ("A", "dog", 50, 2000 * 50, 0, 1200 * 50),
        ("B", "only", 10, 1000, 100, 300),
    ]
    return pd.DataFrame(
        rows, columns=["division", "product", "qty", "gross_sales", "discounts", "food_cost"]
    )


def test_kasavana_smith_quadrants():
    me = menu_engineering(toy_sales()).set_index("product")
    assert me.loc["star", "class"] == "Star"
    assert me.loc["plowhorse", "class"] == "Plowhorse"
    assert me.loc["puzzle", "class"] == "Puzzle"
    assert me.loc["dog", "class"] == "Dog"
    assert me.loc["star", "popularity_threshold"] == pytest.approx(0.7 / 4)


def test_contribution_uses_net_revenue():
    me = menu_engineering(toy_sales()).set_index("product")
    assert me.loc["only", "net_sales"] == 900
    assert me.loc["only", "unit_cm"] == pytest.approx((900 - 300) / 10)


def test_cm_threshold_is_sales_weighted():
    me = menu_engineering(toy_sales())
    a = me[me.division == "A"]
    expected = a["total_cm"].sum() / a["qty"].sum()
    assert a["cm_threshold"].iloc[0] == pytest.approx(expected)


def test_abc_classes_are_ordered():
    items = pd.DataFrame({"product": list("abcdef"), "total_cm": [50, 30, 10, 5, 3, 2]})
    res = abc_analysis(items)
    assert res["abc"].tolist() == ["A", "A", "B", "B", "C", "C"]
    assert res["cum_share"].iloc[-1] == pytest.approx(1.0)


def test_yield_adjusts_gross_quantity():
    recipes = pd.DataFrame(
        {
            "product_id": ["1", "1"],
            "ingredient": ["Palta", "Pan"],
            "qty": [50, 1],
            "unit": ["g", "UN"],
            "yield_pct": [50, 100],
        }
    )
    qty = pd.DataFrame({"product_id": ["1", "1"], "qty": [10, 30]})
    costs = pd.DataFrame({"ingredient": ["palta", "Pan"], "unit_cost": [5000, 200]})
    u = ingredient_usage(qty, recipes, costs).set_index("ingredient")
    assert u.loc["Palta", "net_qty"] == pytest.approx(2.0)  # 40 x 50 g = 2 kg
    assert u.loc["Palta", "gross_qty"] == pytest.approx(4.0)  # 50% yield
    assert u.loc["Palta", "waste_cost"] == pytest.approx(2.0 * 5000)
    assert u.loc["Pan", "waste_qty"] == 0


def test_break_even():
    be = break_even(
        sales=100.0, fixed_costs=40.0, food_cost_pct=0.30, card_fee_pct=0.02, card_share=0.5
    )
    assert be.cm_ratio == pytest.approx(0.69)
    assert be.break_even_sales == pytest.approx(40 / 0.69)
    assert be.operating_profit == pytest.approx(100 * 0.69 - 40)
    assert be.with_food_cost(0.40).break_even_sales > be.break_even_sales
    with pytest.raises(ValueError):
        break_even(100, 40, food_cost_pct=30)


def test_shipped_data_is_consistent():
    d = load()
    m = d.monthly_sales
    assert set(m["month"]) == {"2023-02", "2023-07", "2023-08", "2023-09"}
    assert (m["qty"] > 0).all()
    # Only POS "adjustment" lines (e.g. swapping a topping) may carry a negative cost
    regular = ~m["product"].str.startswith("Ajuste")
    assert (m.loc[regular, "food_cost"] >= 0).all()
    assert d.recipes["yield_pct"].between(1, 100).all()
    assert d.recipes["product_id"].isin(d.daily_qty["product_id"]).mean() > 0.8
    assert not m["product"].str.contains("colonia", case=False).any()
