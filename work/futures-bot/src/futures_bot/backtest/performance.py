from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


TRADING_DAYS_PER_YEAR = Decimal("252")


@dataclass(frozen=True)
class EquityPoint:
    day: date
    equity: Decimal

    def __post_init__(self) -> None:
        if self.equity <= 0:
            raise ValueError("equity must be positive")


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal


def calculate_performance(equity_curve: tuple[EquityPoint, ...]) -> PerformanceMetrics:
    if len(equity_curve) < 2:
        raise ValueError("at least two equity points are required")

    ordered_curve = tuple(sorted(equity_curve, key=lambda point: point.day))
    total_return = (ordered_curve[-1].equity / ordered_curve[0].equity) - Decimal("1")
    max_drawdown = _calculate_max_drawdown(ordered_curve)
    returns = _daily_returns(ordered_curve)
    sharpe_ratio = _annualized_sharpe(returns)

    return PerformanceMetrics(
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
    )


def _calculate_max_drawdown(equity_curve: tuple[EquityPoint, ...]) -> Decimal:
    peak = equity_curve[0].equity
    max_drawdown = Decimal("0")

    for point in equity_curve:
        if point.equity > peak:
            peak = point.equity
        drawdown = (peak - point.equity) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def _daily_returns(equity_curve: tuple[EquityPoint, ...]) -> tuple[Decimal, ...]:
    return tuple(
        (equity_curve[index].equity / equity_curve[index - 1].equity) - Decimal("1")
        for index in range(1, len(equity_curve))
    )


def _annualized_sharpe(returns: tuple[Decimal, ...]) -> Decimal:
    if len(returns) < 2:
        return Decimal("0")

    mean_return = sum(returns, Decimal("0")) / Decimal(len(returns))
    squared_deviations = tuple((daily_return - mean_return) ** 2 for daily_return in returns)
    sample_variance = sum(squared_deviations, Decimal("0")) / Decimal(len(returns) - 1)
    if sample_variance == 0:
        return Decimal("0")

    return (mean_return / sample_variance.sqrt()) * TRADING_DAYS_PER_YEAR.sqrt()
