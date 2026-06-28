from datetime import datetime, timedelta, timezone
from decimal import Decimal

from futures_bot.application.order_activity import OrderActivityTracker
from futures_bot.domain.enums import OrderSide, OrderType
from futures_bot.domain.orders import OrderIntent
from futures_bot.ports.audit import InMemoryAuditLog


NOW = datetime(2026, 6, 28, 14, 37, tzinfo=timezone.utc)


def _intent(client_order_id: str = "order-1") -> OrderIntent:
    return OrderIntent(
        instrument_id="ES-202609-CME",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("5000.25"),
        client_order_id=client_order_id,
    )


def test_order_activity_records_submission_and_builds_risk_inputs():
    audit_log = InMemoryAuditLog()
    tracker = OrderActivityTracker(audit_log)

    tracker.record_submission(
        intent=_intent(),
        timestamp=NOW,
        broker_order_id="broker-123",
    )
    snapshot = tracker.snapshot(now=NOW, recent_order_window=timedelta(minutes=1))

    assert snapshot.used_client_order_ids == frozenset({"order-1"})
    assert snapshot.recent_order_timestamps == (NOW,)
    assert audit_log.events == (
        {
            "type": "order_activity_recorded",
            "timestamp": "2026-06-28T14:37:00+00:00",
            "client_order_id": "order-1",
            "broker_order_id": "broker-123",
            "instrument_id": "ES-202609-CME",
            "side": "buy",
            "quantity": 1,
            "order_type": "limit",
            "limit_price": "5000.25",
        },
    )


def test_order_activity_snapshot_excludes_orders_outside_recent_window():
    tracker = OrderActivityTracker(InMemoryAuditLog())

    tracker.record_submission(
        intent=_intent("old-order"),
        timestamp=NOW - timedelta(minutes=5),
        broker_order_id="broker-old",
    )
    tracker.record_submission(
        intent=_intent("new-order"),
        timestamp=NOW - timedelta(seconds=20),
        broker_order_id="broker-new",
    )
    snapshot = tracker.snapshot(now=NOW, recent_order_window=timedelta(minutes=1))

    assert snapshot.used_client_order_ids == frozenset({"old-order", "new-order"})
    assert snapshot.recent_order_timestamps == (NOW - timedelta(seconds=20),)


def test_order_activity_rejects_duplicate_client_order_id():
    tracker = OrderActivityTracker(InMemoryAuditLog())
    tracker.record_submission(
        intent=_intent(),
        timestamp=NOW,
        broker_order_id="broker-123",
    )

    try:
        tracker.record_submission(
            intent=_intent(),
            timestamp=NOW + timedelta(seconds=1),
            broker_order_id="broker-456",
        )
    except ValueError as exc:
        assert str(exc) == "client order ID was already recorded"
    else:
        raise AssertionError("expected duplicate client order ID to be rejected")


def test_order_activity_snapshot_requires_positive_recent_window():
    tracker = OrderActivityTracker(InMemoryAuditLog())

    try:
        tracker.snapshot(now=NOW, recent_order_window=timedelta(0))
    except ValueError as exc:
        assert str(exc) == "recent_order_window must be positive"
    else:
        raise AssertionError("expected invalid recent window to be rejected")
