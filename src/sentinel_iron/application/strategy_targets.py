from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sentinel_iron.domain.instruments import FuturesInstrument
from sentinel_iron.portfolio.position_sizing import (
    PortfolioRiskCapConfig,
    PositionSizingConfig,
    PositionTarget,
    StrategySignal,
    calculate_volatility_target_position,
    cap_position_targets_by_gross_risk,
)


def build_strategy_position_targets(
    signals: tuple[StrategySignal, ...],
    instruments: Mapping[str, FuturesInstrument],
    dollar_volatility_by_instrument: Mapping[str, Decimal],
    account_equity: Decimal,
    trading_day: date,
    sizing_config: PositionSizingConfig,
    portfolio_config: PortfolioRiskCapConfig,
) -> tuple[PositionTarget, ...]:
    seen_instrument_ids: set[str] = set()
    raw_targets: list[PositionTarget] = []

    for signal in signals:
        if signal.instrument_id in seen_instrument_ids:
            raise ValueError("signal instrument IDs must be unique")
        seen_instrument_ids.add(signal.instrument_id)

        try:
            instrument = instruments[signal.instrument_id]
        except KeyError as exc:
            raise ValueError(f"instrument is required for {signal.instrument_id}") from exc
        if instrument.instrument_id != signal.instrument_id:
            raise ValueError(f"instrument mismatch for {signal.instrument_id}")

        if signal.score == 0 or not instrument.can_trade_on(trading_day):
            raw_targets.append(PositionTarget(signal.instrument_id, 0))
            continue

        try:
            dollar_volatility = dollar_volatility_by_instrument[signal.instrument_id]
        except KeyError as exc:
            raise ValueError(
                f"dollar volatility is required for {signal.instrument_id}"
            ) from exc

        raw_targets.append(
            calculate_volatility_target_position(
                signal=signal,
                account_equity=account_equity,
                dollar_volatility_per_contract=dollar_volatility,
                config=sizing_config,
            )
        )

    nonzero_targets = tuple(target for target in raw_targets if target.quantity != 0)
    if not nonzero_targets:
        return tuple(raw_targets)

    capped_targets = cap_position_targets_by_gross_risk(
        targets=nonzero_targets,
        dollar_volatility_by_instrument=dollar_volatility_by_instrument,
        account_equity=account_equity,
        config=portfolio_config,
    )
    capped_targets_by_instrument = {
        target.instrument_id: target for target in capped_targets
    }

    return tuple(
        capped_targets_by_instrument.get(target.instrument_id, target)
        for target in raw_targets
    )
