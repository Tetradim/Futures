from __future__ import annotations

from decimal import Decimal

from futures_bot.strategies.trend_following import PricePoint


def calculate_dollar_volatility(
    prices: tuple[PricePoint, ...],
    multiplier: Decimal,
    lookback_changes: int,
) -> Decimal | None:
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")
    if lookback_changes < 2:
        raise ValueError("lookback_changes must be at least 2")

    ordered_prices = tuple(sorted(prices, key=lambda point: point.day))
    if len(ordered_prices) < lookback_changes + 1:
        return None

    recent_prices = ordered_prices[-(lookback_changes + 1) :]
    changes = tuple(
        recent_prices[index].close - recent_prices[index - 1].close
        for index in range(1, len(recent_prices))
    )
    mean_change = sum(changes, Decimal("0")) / Decimal(len(changes))
    squared_deviations = tuple((change - mean_change) ** 2 for change in changes)
    sample_variance = sum(squared_deviations, Decimal("0")) / Decimal(len(changes) - 1)
    point_volatility = sample_variance.sqrt()
    return point_volatility * multiplier
