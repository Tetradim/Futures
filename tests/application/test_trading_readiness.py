from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sentinel_iron.application.broker_connection import BrokerConnectionResult
from sentinel_iron.application.reconciliation import ReconciliationResult
from sentinel_iron.application.trading_readiness import (
    TradingReadinessConfig,
    TradingReadinessService,
)
from sentinel_iron.domain.portfolio import AccountSnapshot, Position
from sentinel_iron.ports.audit import InMemoryAuditLog


NOW = datetime(2026, 6, 28, 14, 34, tzinfo=timezone.utc)


def _account(timestamp: datetime = NOW) -> AccountSnapshot:
    return AccountSnapshot(
        account_id="acct-1",
        equity=Decimal("100000"),
        initial_margin=Decimal("10000"),
        maintenance_margin=Decimal("8000"),
        buying_power=Decimal("50000"),
        timestamp=timestamp,
    )


def _position() -> Position:
    return Position(
        instrument_id="ES-202609-CME",
        quantity=2,
        average_price=Decimal("5000.25"),
    )


def _connection(
    connected: bool = True,
    account: AccountSnapshot | None = None,
    positions: tuple[Position, ...] | None = None,
    reason: str | None = None,
) -> BrokerConnectionResult:
    return BrokerConnectionResult(
        connected=connected,
        account=_account() if account is None and connected else account,
        positions=(_position(),) if positions is None and connected else positions or (),
        reason=reason,
    )


def _reconciliation(
    reconciled: bool = True,
    mismatches: tuple[str, ...] = (),
) -> ReconciliationResult:
    return ReconciliationResult(positions_reconciled=reconciled, mismatches=mismatches)


def _service() -> tuple[TradingReadinessService, InMemoryAuditLog]:
    audit_log = InMemoryAuditLog()
    return TradingReadinessService(audit_log), audit_log


def _config() -> TradingReadinessConfig:
    return TradingReadinessConfig(account_stale_after=timedelta(seconds=5))


def test_trading_readiness_config_requires_positive_stale_threshold():
    try:
        TradingReadinessConfig(account_stale_after=timedelta(0))
    except ValueError as exc:
        assert str(exc) == "account_stale_after must be positive"
    else:
        raise AssertionError("expected invalid stale threshold to be rejected")


def test_trading_readiness_approves_connected_fresh_reconciled_session():
    service, audit_log = _service()

    result = service.evaluate(
        connection=_connection(),
        reconciliation=_reconciliation(),
        now=NOW,
        config=_config(),
    )

    assert result.ready is True
    assert result.reason is None
    assert result.detail == "ready"
    assert audit_log.events == (
        {
            "type": "trading_readiness",
            "timestamp": "2026-06-28T14:34:00+00:00",
            "ready": True,
            "reason": None,
            "detail": "ready",
            "account_id": "acct-1",
            "position_count": 1,
            "positions_reconciled": True,
            "mismatches": (),
        },
    )


def test_trading_readiness_rejects_disconnected_broker():
    service, audit_log = _service()

    result = service.evaluate(
        connection=_connection(connected=False, reason="gateway unavailable"),
        reconciliation=_reconciliation(),
        now=NOW,
        config=_config(),
    )

    assert result.ready is False
    assert result.reason == "broker_not_connected"
    assert result.detail == "gateway unavailable"
    assert audit_log.events[-1]["ready"] is False
    assert audit_log.events[-1]["reason"] == "broker_not_connected"


def test_trading_readiness_rejects_stale_account_snapshot():
    service, audit_log = _service()

    result = service.evaluate(
        connection=_connection(account=_account(timestamp=NOW - timedelta(seconds=6))),
        reconciliation=_reconciliation(),
        now=NOW,
        config=_config(),
    )

    assert result.ready is False
    assert result.reason == "stale_account_snapshot"
    assert result.detail == "account snapshot is stale"
    assert audit_log.events[-1]["account_id"] == "acct-1"
    assert audit_log.events[-1]["reason"] == "stale_account_snapshot"


def test_trading_readiness_rejects_unreconciled_positions():
    service, audit_log = _service()

    result = service.evaluate(
        connection=_connection(),
        reconciliation=_reconciliation(
            reconciled=False,
            mismatches=("quantity mismatch for ES-202609-CME: internal=1 broker=2",),
        ),
        now=NOW,
        config=_config(),
    )

    assert result.ready is False
    assert result.reason == "positions_not_reconciled"
    assert result.detail == "quantity mismatch for ES-202609-CME: internal=1 broker=2"
    assert audit_log.events[-1]["positions_reconciled"] is False
    assert audit_log.events[-1]["mismatches"] == (
        "quantity mismatch for ES-202609-CME: internal=1 broker=2",
    )
