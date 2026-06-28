from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from futures_bot.application.broker_connection import BrokerConnectionResult
from futures_bot.application.reconciliation import ReconciliationResult
from futures_bot.ports.audit import AuditLogPort


@dataclass(frozen=True)
class TradingReadinessConfig:
    account_stale_after: timedelta

    def __post_init__(self) -> None:
        if self.account_stale_after <= timedelta(0):
            raise ValueError("account_stale_after must be positive")


@dataclass(frozen=True)
class TradingReadinessResult:
    ready: bool
    reason: str | None
    detail: str


class TradingReadinessService:
    def __init__(self, audit_log: AuditLogPort) -> None:
        self._audit_log = audit_log

    def evaluate(
        self,
        connection: BrokerConnectionResult,
        reconciliation: ReconciliationResult,
        now: datetime,
        config: TradingReadinessConfig,
    ) -> TradingReadinessResult:
        if not connection.connected:
            result = TradingReadinessResult(
                ready=False,
                reason="broker_not_connected",
                detail=connection.reason or "broker connection is not active",
            )
        elif connection.account is None:
            result = TradingReadinessResult(
                ready=False,
                reason="missing_account_snapshot",
                detail="account snapshot is missing",
            )
        elif now - connection.account.timestamp > config.account_stale_after:
            result = TradingReadinessResult(
                ready=False,
                reason="stale_account_snapshot",
                detail="account snapshot is stale",
            )
        elif not reconciliation.positions_reconciled:
            result = TradingReadinessResult(
                ready=False,
                reason="positions_not_reconciled",
                detail="; ".join(reconciliation.mismatches),
            )
        else:
            result = TradingReadinessResult(
                ready=True,
                reason=None,
                detail="ready",
            )

        self._audit_log.append(
            {
                "type": "trading_readiness",
                "timestamp": now.isoformat(),
                "ready": result.ready,
                "reason": result.reason,
                "detail": result.detail,
                "account_id": connection.account.account_id if connection.account is not None else None,
                "position_count": len(connection.positions),
                "positions_reconciled": reconciliation.positions_reconciled,
                "mismatches": reconciliation.mismatches,
            }
        )
        return result
