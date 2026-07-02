from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ContractLiquidity:
    instrument_id: str
    volume: int
    open_interest: int
    last_safe_trade_date: date

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.open_interest < 0:
            raise ValueError("open_interest cannot be negative")


@dataclass(frozen=True)
class RollConfig:
    days_before_last_safe_trade: int
    liquidity_ratio: float

    def __post_init__(self) -> None:
        if self.days_before_last_safe_trade < 0:
            raise ValueError("days_before_last_safe_trade cannot be negative")
        if self.liquidity_ratio <= 1:
            raise ValueError("liquidity_ratio must be greater than 1")


@dataclass(frozen=True)
class RollDecision:
    should_roll: bool
    from_instrument_id: str
    to_instrument_id: str
    reason: str


def evaluate_roll(
    today: date,
    current: ContractLiquidity,
    next_contract: ContractLiquidity,
    config: RollConfig,
) -> RollDecision:
    roll_window_start = current.last_safe_trade_date - timedelta(
        days=config.days_before_last_safe_trade
    )
    if today >= roll_window_start:
        return _roll(current, next_contract, "inside_roll_window")

    if _dominates(next_contract.volume, current.volume, config.liquidity_ratio):
        return _roll(current, next_contract, "next_volume_dominates")

    if _dominates(next_contract.open_interest, current.open_interest, config.liquidity_ratio):
        return _roll(current, next_contract, "next_open_interest_dominates")

    return RollDecision(
        should_roll=False,
        from_instrument_id=current.instrument_id,
        to_instrument_id=current.instrument_id,
        reason="hold_current",
    )


def _dominates(next_value: int, current_value: int, ratio: float) -> bool:
    if current_value == 0:
        return next_value > 0
    return next_value / current_value >= ratio


def _roll(
    current: ContractLiquidity,
    next_contract: ContractLiquidity,
    reason: str,
) -> RollDecision:
    return RollDecision(
        should_roll=True,
        from_instrument_id=current.instrument_id,
        to_instrument_id=next_contract.instrument_id,
        reason=reason,
    )
