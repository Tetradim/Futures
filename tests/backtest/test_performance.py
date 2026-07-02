from datetime import date
from decimal import Decimal

import pytest

from sentinel_iron.backtest.performance import EquityPoint, calculate_performance


def test_performance_calculates_total_return_and_max_drawdown():
    performance = calculate_performance(
        (
            EquityPoint(day=date(2026, 1, 1), equity=Decimal("100000")),
            EquityPoint(day=date(2026, 1, 2), equity=Decimal("110000")),
            EquityPoint(day=date(2026, 1, 3), equity=Decimal("99000")),
            EquityPoint(day=date(2026, 1, 4), equity=Decimal("120000")),
        )
    )

    assert performance.total_return == Decimal("0.20")
    assert performance.max_drawdown == Decimal("0.10")


def test_performance_calculates_annualized_sharpe_from_daily_returns():
    performance = calculate_performance(
        (
            EquityPoint(day=date(2026, 1, 1), equity=Decimal("100")),
            EquityPoint(day=date(2026, 1, 2), equity=Decimal("101")),
            EquityPoint(day=date(2026, 1, 3), equity=Decimal("100")),
            EquityPoint(day=date(2026, 1, 4), equity=Decimal("102")),
        )
    )

    assert performance.sharpe_ratio.quantize(Decimal("0.0001")) == Decimal("6.9872")


def test_performance_uses_date_order_not_input_order():
    performance = calculate_performance(
        (
            EquityPoint(day=date(2026, 1, 3), equity=Decimal("121")),
            EquityPoint(day=date(2026, 1, 1), equity=Decimal("100")),
            EquityPoint(day=date(2026, 1, 2), equity=Decimal("110")),
        )
    )

    assert performance.total_return == Decimal("0.21")


def test_performance_requires_at_least_two_equity_points():
    with pytest.raises(ValueError, match="at least two equity points are required"):
        calculate_performance((EquityPoint(day=date(2026, 1, 1), equity=Decimal("100")),))


def test_equity_point_rejects_non_positive_equity():
    with pytest.raises(ValueError, match="equity must be positive"):
        EquityPoint(day=date(2026, 1, 1), equity=Decimal("0"))
