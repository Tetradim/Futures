from datetime import date
from decimal import Decimal

import pytest

from futures_bot.market.volatility import calculate_dollar_volatility
from futures_bot.strategies.trend_following import PricePoint


def _prices(values: list[str]) -> tuple[PricePoint, ...]:
    return tuple(
        PricePoint(day=date(2026, 1, index + 1), close=Decimal(value))
        for index, value in enumerate(values)
    )


def test_calculates_multiplier_adjusted_sample_standard_deviation_of_price_changes():
    volatility = calculate_dollar_volatility(
        prices=_prices(["100", "101", "103", "106"]),
        multiplier=Decimal("50"),
        lookback_changes=3,
    )

    assert volatility == Decimal("50")


def test_uses_most_recent_price_changes_for_lookback_window():
    volatility = calculate_dollar_volatility(
        prices=_prices(["100", "110", "111", "113", "116"]),
        multiplier=Decimal("10"),
        lookback_changes=3,
    )

    assert volatility == Decimal("10")


def test_returns_none_when_not_enough_price_history():
    volatility = calculate_dollar_volatility(
        prices=_prices(["100", "101"]),
        multiplier=Decimal("50"),
        lookback_changes=3,
    )

    assert volatility is None


def test_rejects_non_positive_multiplier():
    with pytest.raises(ValueError, match="multiplier must be positive"):
        calculate_dollar_volatility(
            prices=_prices(["100", "101", "102", "103"]),
            multiplier=Decimal("0"),
            lookback_changes=3,
        )


def test_rejects_lookback_shorter_than_two_changes():
    with pytest.raises(ValueError, match="lookback_changes must be at least 2"):
        calculate_dollar_volatility(
            prices=_prices(["100", "101", "102"]),
            multiplier=Decimal("50"),
            lookback_changes=1,
        )
