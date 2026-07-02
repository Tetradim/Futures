from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class WeightedSignal:
    name: str
    score: Decimal
    weight: Decimal

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name is required")
        if self.weight <= 0:
            raise ValueError("weight must be positive")


@dataclass(frozen=True)
class CompositeSignal:
    instrument_id: str
    score: Decimal
    components: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", MappingProxyType(dict(self.components)))


def combine_weighted_signals(
    instrument_id: str,
    signals: tuple[WeightedSignal, ...],
) -> CompositeSignal:
    if not instrument_id:
        raise ValueError("instrument_id is required")
    if not signals:
        raise ValueError("signals are required")

    names = [signal.name for signal in signals]
    if len(set(names)) != len(names):
        raise ValueError("signal names must be unique")

    total_weight = sum((signal.weight for signal in signals), Decimal("0"))
    raw_score = sum((signal.score * signal.weight for signal in signals), Decimal("0")) / total_weight

    return CompositeSignal(
        instrument_id=instrument_id,
        score=_clip(raw_score),
        components={signal.name: signal.score for signal in signals},
    )


def _clip(score: Decimal) -> Decimal:
    if score > Decimal("1"):
        return Decimal("1")
    if score < Decimal("-1"):
        return Decimal("-1")
    return score
