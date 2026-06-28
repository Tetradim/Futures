from datetime import datetime, timezone

from futures_bot.application.order_cancellation import (
    OrderCancellationRequest,
    OrderCancellationService,
)
from futures_bot.domain.order_lifecycle import OrderLifecycle, OrderLifecycleStatus
from futures_bot.domain.orders import BrokerOrder
from futures_bot.domain.portfolio import AccountSnapshot, Position
from futures_bot.ports.audit import InMemoryAuditLog
from futures_bot.ports.broker import BrokerCancellationError


NOW = datetime(2026, 6, 28, 14, 32, tzinfo=timezone.utc)


class RecordingBroker:
    def __init__(self) -> None:
        self.canceled_order_ids: list[str] = []

    def connect(self) -> None:
        pass

    def get_account(self) -> AccountSnapshot:
        raise NotImplementedError

    def get_positions(self) -> tuple[Position, ...]:
        raise NotImplementedError

    def submit_order(self, order: BrokerOrder) -> str:
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str) -> None:
        self.canceled_order_ids.append(broker_order_id)


class RejectingCancelBroker(RecordingBroker):
    def cancel_order(self, broker_order_id: str) -> None:
        self.canceled_order_ids.append(broker_order_id)
        raise BrokerCancellationError(
            reason="broker rejected cancel: too late to cancel",
            broker_error_code="TOO_LATE_TO_CANCEL",
        )


class RecordingLifecycleStore:
    def __init__(self, loaded_lifecycle: OrderLifecycle | None = None) -> None:
        self.loaded_lifecycle = loaded_lifecycle
        self.loaded_client_order_ids: list[str] = []
        self.saved_lifecycles: list[OrderLifecycle] = []

    def load(self, client_order_id: str) -> OrderLifecycle | None:
        self.loaded_client_order_ids.append(client_order_id)
        return self.loaded_lifecycle

    def save(self, lifecycle: OrderLifecycle) -> None:
        self.saved_lifecycles.append(lifecycle)


def _request(**overrides: object) -> OrderCancellationRequest:
    values = {
        "account_id": "acct-1",
        "client_order_id": "order-1",
        "broker_order_id": "broker-123",
        "instrument_id": "ES-202609-CME",
        "timestamp": NOW,
    }
    values.update(overrides)
    return OrderCancellationRequest(**values)


def test_order_cancellation_requests_cancel_and_audits_pending_cancel():
    audit_log = InMemoryAuditLog()
    broker = RecordingBroker()
    service = OrderCancellationService(broker=broker, audit_log=audit_log)
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    result = service.request_cancel(lifecycle, _request())

    assert result.cancellation_requested is True
    assert result.lifecycle.status == OrderLifecycleStatus.PENDING_CANCEL
    assert result.reason is None
    assert result.broker_error_code is None
    assert broker.canceled_order_ids == ["broker-123"]
    assert audit_log.events == (
        {
            "type": "order_cancel_requested",
            "timestamp": "2026-06-28T14:32:00+00:00",
            "account_id": "acct-1",
            "client_order_id": "order-1",
            "broker_order_id": "broker-123",
            "instrument_id": "ES-202609-CME",
            "previous_status": "working",
            "status": "pending_cancel",
        },
    )


def test_order_cancellation_persists_pending_cancel_when_store_is_configured():
    audit_log = InMemoryAuditLog()
    broker = RecordingBroker()
    lifecycle_store = RecordingLifecycleStore()
    service = OrderCancellationService(
        broker=broker,
        audit_log=audit_log,
        lifecycle_store=lifecycle_store,
    )
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    result = service.request_cancel(lifecycle, _request())

    assert result.cancellation_requested is True
    assert lifecycle_store.saved_lifecycles == [result.lifecycle]
    assert lifecycle_store.saved_lifecycles[0].status == OrderLifecycleStatus.PENDING_CANCEL


def test_order_cancellation_recovers_lifecycle_from_store_after_restart():
    audit_log = InMemoryAuditLog()
    broker = RecordingBroker()
    lifecycle_store = RecordingLifecycleStore(
        OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()
    )
    service = OrderCancellationService(
        broker=broker,
        audit_log=audit_log,
        lifecycle_store=lifecycle_store,
    )

    result = service.request_cancel(None, _request())

    assert lifecycle_store.loaded_client_order_ids == ["order-1"]
    assert result.lifecycle.status == OrderLifecycleStatus.PENDING_CANCEL
    assert lifecycle_store.saved_lifecycles == [result.lifecycle]
    assert broker.canceled_order_ids == ["broker-123"]


def test_order_cancellation_rejects_missing_lifecycle_after_restart():
    audit_log = InMemoryAuditLog()
    broker = RecordingBroker()
    lifecycle_store = RecordingLifecycleStore()
    service = OrderCancellationService(
        broker=broker,
        audit_log=audit_log,
        lifecycle_store=lifecycle_store,
    )

    try:
        service.request_cancel(None, _request())
    except ValueError as exc:
        assert str(exc) == "order lifecycle was not found"
    else:
        raise AssertionError("expected missing lifecycle to be rejected")

    assert lifecycle_store.loaded_client_order_ids == ["order-1"]
    assert lifecycle_store.saved_lifecycles == []
    assert broker.canceled_order_ids == []
    assert audit_log.events == ()


def test_order_cancellation_audits_broker_cancel_rejection_without_advancing_lifecycle():
    audit_log = InMemoryAuditLog()
    broker = RejectingCancelBroker()
    service = OrderCancellationService(broker=broker, audit_log=audit_log)
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    result = service.request_cancel(lifecycle, _request())

    assert result.cancellation_requested is False
    assert result.lifecycle == lifecycle
    assert result.reason == "broker rejected cancel: too late to cancel"
    assert result.broker_error_code == "TOO_LATE_TO_CANCEL"
    assert broker.canceled_order_ids == ["broker-123"]
    assert audit_log.events[-1] == {
        "type": "order_cancel_failed",
        "timestamp": "2026-06-28T14:32:00+00:00",
        "account_id": "acct-1",
        "client_order_id": "order-1",
        "broker_order_id": "broker-123",
        "instrument_id": "ES-202609-CME",
        "status": "working",
        "reason": "broker_cancellation_error",
        "detail": "broker rejected cancel: too late to cancel",
        "broker_error_code": "TOO_LATE_TO_CANCEL",
    }


def test_order_cancellation_does_not_persist_when_broker_rejects_cancel():
    audit_log = InMemoryAuditLog()
    broker = RejectingCancelBroker()
    lifecycle_store = RecordingLifecycleStore()
    service = OrderCancellationService(
        broker=broker,
        audit_log=audit_log,
        lifecycle_store=lifecycle_store,
    )
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    result = service.request_cancel(lifecycle, _request())

    assert result.cancellation_requested is False
    assert result.lifecycle == lifecycle
    assert lifecycle_store.saved_lifecycles == []


def test_order_cancellation_rejects_mismatched_client_order_id_before_broker_call():
    audit_log = InMemoryAuditLog()
    broker = RecordingBroker()
    service = OrderCancellationService(broker=broker, audit_log=audit_log)

    try:
        service.request_cancel(
            OrderLifecycle.pending_submit(client_order_id="order-1").mark_working(),
            _request(client_order_id="order-2"),
        )
    except ValueError as exc:
        assert str(exc) == "cancel request client_order_id does not match lifecycle"
    else:
        raise AssertionError("expected mismatched cancel request to be rejected")

    assert broker.canceled_order_ids == []
    assert audit_log.events == ()
