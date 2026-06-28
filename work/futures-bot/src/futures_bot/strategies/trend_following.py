from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PricePoint:
    day: date
    close: Decimal

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")


@dataclass(frozen=True)
class TrendSignalConfig:
    lookbacks: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.lookbacks:
            raise ValueError("lookbacks are required")
        if any(lookback <= 0 for lookback in self.lookbacks):
            raise ValueError("lookbacks must be positive")


@dataclass(frozen=True)
class TrendSignal:
    instrument_id: str
    score: Decimal
    components: tuple[Decimal, ...]
    lookbacks: tuple[int, ...]


def calculate_trend_signal(
    instrument_id: str,
    prices: tuple[PricePoint, ...],
    config: TrendSignalConfig,
) -> TrendSignal:
    if not instrument_id:
        raise ValueError("instrument_id is required")

    ordered_prices = tuple(sorted(prices, key=lambda point: point.day))
    if not ordered_prices:
        return TrendSignal(instrument_id=instrument_id, score=Decimal("0"), components=(), lookbacks=())

    current_close = ordered_prices[-1].close
    components: list[Decimal] = []
    active_lookbacks: list[int] = []

    for lookback in config.lookbacks:
        if len(ordered_prices) <= lookback:
            continue
        prior_close = ordered_prices[-(lookback + 1)].close
        components.append(_sign(current_close - prior_close))
        active_lookbacks.append(lookback)

    if not components:
        score = Decimal("0")
    else:
        score = sum(components, Decimal("0")) / Decimal(len(components))

    return TrendSignal(
        instrument_id=instrument_id,
        score=score,
        components=tuple(components),
        lookbacks=tuple(active_lookbacks),
    )


def _sign(value: Decimal) -> Decimal:
    if value > 0:
        return Decimal("1")
    if value < 0:
        return Decimal("-1")
    return Decimal("0")
