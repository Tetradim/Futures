from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sentinel_iron.application.order_activity import OrderActivityTracker
from sentinel_iron.application.risk_check import RiskCheckService
from sentinel_iron.domain.order_lifecycle import OrderLifecycle
from sentinel_iron.domain.orders import BrokerOrder, OrderIntent
from sentinel_iron.ports.audit import AuditLogPort
from sentinel_iron.ports.broker import BrokerPort, BrokerSubmissionError
from sentinel_iron.risk.engine import RiskContext, RiskDecision


@dataclass(frozen=True)
class OrderSubmissionResult:
    risk_decision: RiskDecision
    lifecycle: OrderLifecycle
    broker_order_id: str | None


class OrderLifecycleStorePort(Protocol):
    def load(self, client_order_id: str) -> OrderLifecycle | None:
        """Load the latest persisted lifecycle for a client order ID."""

    def save(self, lifecycle: OrderLifecycle) -> None:
        """Persist the latest known order lifecycle."""


class OrderSubmissionService:
    def __init__(
        self,
        risk_check: RiskCheckService,
        broker: BrokerPort,
        audit_log: AuditLogPort,
        activity_tracker: OrderActivityTracker | None = None,
        lifecycle_store: OrderLifecycleStorePort | None = None,
    ) -> None:
        self._risk_check = risk_check
        self._broker = broker
        self._audit_log = audit_log
        self._activity_tracker = activity_tracker
        self._lifecycle_store = lifecycle_store

    def submit(self, intent: OrderIntent, context: RiskContext) -> OrderSubmissionResult:
        risk_decision = self._risk_check.check(intent, context)
        lifecycle = OrderLifecycle.pending_submit(client_order_id=intent.client_order_id)

        if not risk_decision.approved:
            rejected = lifecycle.mark_rejected(risk_decision.detail)
            self._save_lifecycle(rejected)
            self._audit_log.append(
                {
                    "type": "order_submission_blocked",
                    "timestamp": context.now.isoformat(),
                    "account_id": context.account.account_id,
                    "client_order_id": intent.client_order_id,
                    "instrument_id": intent.instrument_id,
                    "status": rejected.status.value,
                    "reason": risk_decision.reason.value if risk_decision.reason is not None else None,
                    "detail": risk_decision.detail,
                }
            )
            return OrderSubmissionResult(
                risk_decision=risk_decision,
                lifecycle=rejected,
                broker_order_id=None,
            )

        broker_order = BrokerOrder.from_intent(intent)
        try:
            broker_order_id = self._broker.submit_order(broker_order)
        except BrokerSubmissionError as exc:
            rejected = lifecycle.mark_rejected(exc.reason)
            self._save_lifecycle(rejected)
            self._audit_log.append(
                {
                    "type": "order_submission_failed",
                    "timestamp": context.now.isoformat(),
                    "account_id": context.account.account_id,
                    "client_order_id": intent.client_order_id,
                    "instrument_id": intent.instrument_id,
                    "status": rejected.status.value,
                    "reason": "broker_submission_error",
                    "detail": exc.reason,
                    "broker_error_code": exc.broker_error_code,
                }
            )
            return OrderSubmissionResult(
                risk_decision=risk_decision,
                lifecycle=rejected,
                broker_order_id=None,
            )

        working = lifecycle.mark_working()
        self._save_lifecycle(working)
        self._audit_log.append(
            {
                "type": "order_submitted",
                "timestamp": context.now.isoformat(),
                "account_id": context.account.account_id,
                "client_order_id": intent.client_order_id,
                "broker_order_id": broker_order_id,
                "instrument_id": intent.instrument_id,
                "status": working.status.value,
            }
        )
        if self._activity_tracker is not None:
            self._activity_tracker.record_submission(
                intent=intent,
                timestamp=context.now,
                broker_order_id=broker_order_id,
            )
        return OrderSubmissionResult(
            risk_decision=risk_decision,
            lifecycle=working,
            broker_order_id=broker_order_id,
        )

    def _save_lifecycle(self, lifecycle: OrderLifecycle) -> None:
        if self._lifecycle_store is not None:
            self._lifecycle_store.save(lifecycle)
