from datetime import datetime, timezone
from decimal import Decimal

from futures_bot.application.margin_estimates import MarginEstimateUnavailable
from futures_bot.application.margin_schedules import (
    MarginScheduleEntry,
    MarginScheduleProvider,
)
from futures_bot.application.rebalance_risk_context import MarginEstimate
from futures_bot.domain.enums import OrderSide, OrderType
from futures_bot.domain.orders import BrokerOrder


NOW = datetime(2026, 6, 28, 16, 45, tzinfo=timezone.utc)
EXPIRES = datetime(2026, 6, 29, 16, 45, tzinfo=timezone.utc)


def _order(instrument_id: str = "ES-202609-CME", quantity: int = 2) -> BrokerOrder:
    return BrokerOrder(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=quantity,
        order_type=OrderType.MARKET,
        client_order_id="order-1",
    )


def _entry(**overrides) -> MarginScheduleEntry:
    values = {
        "instrument_id": "ES-202609-CME",
        "initial_margin_per_contract": Decimal("12000"),
        "maintenance_margin_per_contract": Decimal("10000"),
        "source": "FCM daily margin schedule 2026-06-28",
        "expires_at": EXPIRES,
    }
    values.update(overrides)
    return MarginScheduleEntry(**values)


def test_margin_schedule_provider_multiplies_per_contract_margin_by_quantity():
    provider = MarginScheduleProvider(
        entries={"ES-202609-CME": _entry()},
        clock=lambda: NOW,
    )

    estimate = provider.estimate_order_margin(_order(quantity=3))

    assert estimate == MarginEstimate(
        initial_margin=Decimal("36000"),
        maintenance_margin=Decimal("30000"),
    )


def test_margin_schedule_provider_rejects_missing_instrument_schedule():
    provider = MarginScheduleProvider(entries={}, clock=lambda: NOW)

    try:
        provider.estimate_order_margin(_order())
    except MarginEstimateUnavailable as exc:
        assert exc.reason == "margin schedule is required for ES-202609-CME"
    else:
        raise AssertionError("expected missing margin schedule to be rejected")


def test_margin_schedule_provider_rejects_stale_schedule():
    provider = MarginScheduleProvider(
        entries={
            "ES-202609-CME": _entry(
                expires_at=datetime(2026, 6, 27, 16, 45, tzinfo=timezone.utc)
            )
        },
        clock=lambda: NOW,
    )

    try:
        provider.estimate_order_margin(_order())
    except MarginEstimateUnavailable as exc:
        assert exc.reason == (
            "margin schedule for ES-202609-CME expired at 2026-06-27T16:45:00+00:00"
        )
    else:
        raise AssertionError("expected stale margin schedule to be rejected")


def test_margin_schedule_entry_rejects_missing_source():
    try:
        _entry(source="")
    except ValueError as exc:
        assert str(exc) == "source is required"
    else:
        raise AssertionError("expected missing source to be rejected")


def test_margin_schedule_entry_rejects_non_positive_margin():
    try:
        _entry(initial_margin_per_contract=Decimal("0"))
    except ValueError as exc:
        assert str(exc) == "initial_margin_per_contract must be positive"
    else:
        raise AssertionError("expected non-positive margin to be rejected")
