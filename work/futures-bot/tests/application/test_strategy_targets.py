from datetime import date
from decimal import Decimal

import pytest

from futures_bot.domain.enums import SettlementType
from futures_bot.domain.instruments import ContractSpec, FuturesInstrument, TradingCalendar
from futures_bot.portfolio.position_sizing import (
    PortfolioRiskCapConfig,
    PositionSizingConfig,
    PositionTarget,
)
from futures_bot.strategies.composite import CompositeSignal


def _builder():
    try:
        from futures_bot.application.strategy_targets import build_strategy_position_targets
    except ModuleNotFoundError:
        pytest.fail("expected build_strategy_position_targets to exist")

    return build_strategy_position_targets


def test_build_strategy_position_targets_sizes_and_caps_composite_signals():
    targets = _builder()(
        signals=(
            CompositeSignal("ES-202609-CME", Decimal("1"), {"trend": Decimal("1")}),
            CompositeSignal("NQ-202609-CME", Decimal("-1"), {"trend": Decimal("-1")}),
        ),
        instruments={
            "ES-202609-CME": _instrument("ES-202609-CME"),
            "NQ-202609-CME": _instrument("NQ-202609-CME"),
        },
        dollar_volatility_by_instrument={
            "ES-202609-CME": Decimal("2500"),
            "NQ-202609-CME": Decimal("5000"),
        },
        account_equity=Decimal("100000"),
        trading_day=date(2026, 9, 14),
        sizing_config=PositionSizingConfig(
            target_risk_fraction=Decimal("0.10"),
            max_contracts=10,
        ),
        portfolio_config=PortfolioRiskCapConfig(
            max_gross_risk_fraction=Decimal("0.10")
        ),
    )

    assert targets == (
        PositionTarget("ES-202609-CME", 2),
        PositionTarget("NQ-202609-CME", -1),
    )


def test_build_strategy_position_targets_flattens_unsafe_contract_without_volatility():
    targets = _builder()(
        signals=(
            CompositeSignal("CL-202609-NYMEX", Decimal("1"), {"trend": Decimal("1")}),
        ),
        instruments={
            "CL-202609-NYMEX": _instrument(
                "CL-202609-NYMEX",
                settlement_type=SettlementType.PHYSICAL,
                first_notice_date=date(2026, 8, 31),
                last_trade_date=date(2026, 9, 21),
                last_safe_trade_date=date(2026, 8, 28),
            )
        },
        dollar_volatility_by_instrument={},
        account_equity=Decimal("100000"),
        trading_day=date(2026, 8, 29),
        sizing_config=PositionSizingConfig(
            target_risk_fraction=Decimal("0.10"),
            max_contracts=10,
        ),
        portfolio_config=PortfolioRiskCapConfig(
            max_gross_risk_fraction=Decimal("0.10")
        ),
    )

    assert targets == (PositionTarget("CL-202609-NYMEX", 0),)


def test_build_strategy_position_targets_keeps_zero_signal_flat_without_volatility():
    targets = _builder()(
        signals=(
            CompositeSignal("ES-202609-CME", Decimal("0"), {"trend": Decimal("0")}),
        ),
        instruments={"ES-202609-CME": _instrument("ES-202609-CME")},
        dollar_volatility_by_instrument={},
        account_equity=Decimal("100000"),
        trading_day=date(2026, 9, 14),
        sizing_config=PositionSizingConfig(
            target_risk_fraction=Decimal("0.10"),
            max_contracts=10,
        ),
        portfolio_config=PortfolioRiskCapConfig(
            max_gross_risk_fraction=Decimal("0.10")
        ),
    )

    assert targets == (PositionTarget("ES-202609-CME", 0),)


def test_build_strategy_position_targets_rejects_duplicate_signal_instruments():
    with pytest.raises(ValueError, match="signal instrument IDs must be unique"):
        _builder()(
            signals=(
                CompositeSignal("ES-202609-CME", Decimal("1"), {}),
                CompositeSignal("ES-202609-CME", Decimal("-1"), {}),
            ),
            instruments={"ES-202609-CME": _instrument("ES-202609-CME")},
            dollar_volatility_by_instrument={"ES-202609-CME": Decimal("2500")},
            account_equity=Decimal("100000"),
            trading_day=date(2026, 9, 14),
            sizing_config=PositionSizingConfig(
                target_risk_fraction=Decimal("0.10"),
                max_contracts=10,
            ),
            portfolio_config=PortfolioRiskCapConfig(
                max_gross_risk_fraction=Decimal("0.10")
            ),
        )


def test_build_strategy_position_targets_rejects_missing_instrument():
    with pytest.raises(ValueError, match="instrument is required for ES-202609-CME"):
        _builder()(
            signals=(CompositeSignal("ES-202609-CME", Decimal("1"), {}),),
            instruments={},
            dollar_volatility_by_instrument={"ES-202609-CME": Decimal("2500")},
            account_equity=Decimal("100000"),
            trading_day=date(2026, 9, 14),
            sizing_config=PositionSizingConfig(
                target_risk_fraction=Decimal("0.10"),
                max_contracts=10,
            ),
            portfolio_config=PortfolioRiskCapConfig(
                max_gross_risk_fraction=Decimal("0.10")
            ),
        )


def _instrument(
    instrument_id: str,
    *,
    settlement_type: SettlementType = SettlementType.CASH,
    first_notice_date: date | None = None,
    last_trade_date: date = date(2026, 9, 18),
    last_safe_trade_date: date = date(2026, 9, 14),
) -> FuturesInstrument:
    symbol, contract_month, exchange = instrument_id.split("-")
    return FuturesInstrument(
        instrument_id=instrument_id,
        spec=ContractSpec(
            symbol=symbol,
            exchange=exchange,
            contract_month=contract_month,
            multiplier=Decimal("50"),
            tick_size=Decimal("0.25"),
            currency="USD",
            settlement_type=settlement_type,
        ),
        calendar=TradingCalendar(
            first_notice_date=first_notice_date,
            last_trade_date=last_trade_date,
            last_safe_trade_date=last_safe_trade_date,
        ),
    )
