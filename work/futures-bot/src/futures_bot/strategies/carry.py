from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CurveContract:
    instrument_id: str
    expiration: date
    price: Decimal

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.price <= 0:
            raise ValueError("price must be positive")


@dataclass(frozen=True)
class CarrySignal:
    instrument_id: str
    annualized_carry: Decimal
    score: Decimal


def calculate_carry_signal(
    instrument_id: str,
    front: CurveContract,
    deferred: CurveContract,
) -> CarrySignal:
    if not instrument_id:
        raise ValueError("instrument_id is required")
    days_between_expirations = (deferred.expiration - front.expiration).days
    if days_between_expirations <= 0:
        raise ValueError("deferred expiration must be after front expiration")

    annualized_carry = (
        (front.price - deferred.price)
        / front.price
        * (Decimal("365") / Decimal(days_between_expirations))
    )

    return CarrySignal(
        instrument_id=instrument_id,
        annualized_carry=annualized_carry,
        score=_score_from_carry(annualized_carry),
    )


def _score_from_carry(annualized_carry: Decimal) -> Decimal:
    if annualized_carry > 0:
        return Decimal("1")
    if annualized_carry < 0:
        return Decimal("-1")
    return Decimal("0")
