from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sentinel_iron.domain.order_lifecycle import OrderLifecycle
from sentinel_iron.ports.audit import AuditLogPort
from sentinel_iron.ports.broker import BrokerCancellationError, BrokerPort


@dataclass(frozen=True)
class OrderCancellationRequest:
    account_id: str
    client_order_id: str
    broker_order_id: str
    instrument_id: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id is required")
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if not self.broker_order_id:
            raise ValueError("broker_order_id is required")
        if not self.instrument_id:
            raise ValueError("instrument_id is required")


@dataclass(frozen=True)
class OrderCancellationResult:
    lifecycle: OrderLifecycle
    cancellation_requested: bool
    reason: str | None = None
    broker_error_code: str | None = None


class OrderLifecycleStorePort(Protocol):
    def load(self, client_order_id: str) -> OrderLifecycle | None:
        """Load the latest persisted lifecycle for a client order ID."""

    def save(self, lifecycle: OrderLifecycle) -> None:
        """Persist the latest known order lifecycle."""


class OrderCancellationService:
    def __init__(
        self,
        broker: BrokerPort,
        audit_log: AuditLogPort,
        lifecycle_store: OrderLifecycleStorePort | None = None,
    ) -> None:
        self._broker = broker
        self._audit_log = audit_log
        self._lifecycle_store = lifecycle_store

    def request_cancel(
        self,
        lifecycle: OrderLifecycle | None,
        request: OrderCancellationRequest,
    ) -> OrderCancellationResult:
        if lifecycle is None:
            if self._lifecycle_store is None:
                raise ValueError("order lifecycle is required when lifecycle store is not configured")
            lifecycle = self._lifecycle_store.load(request.client_order_id)
            if lifecycle is None:
                raise ValueError("order lifecycle was not found")
        if request.client_order_id != lifecycle.client_order_id:
            raise ValueError("cancel request client_order_id does not match lifecycle")

        pending_cancel = lifecycle.mark_pending_cancel()
        try:
            self._broker.cancel_order(request.broker_order_id)
        except BrokerCancellationError as exc:
            self._audit_log.append(
                {
                    "type": "order_cancel_failed",
                    "timestamp": request.timestamp.isoformat(),
                    "account_id": request.account_id,
                    "client_order_id": request.client_order_id,
                    "broker_order_id": request.broker_order_id,
                    "instrument_id": request.instrument_id,
                    "status": lifecycle.status.value,
                    "reason": "broker_cancellation_error",
                    "detail": exc.reason,
                    "broker_error_code": exc.broker_error_code,
                }
            )
            return OrderCancellationResult(
                lifecycle=lifecycle,
                cancellation_requested=False,
                reason=exc.reason,
                broker_error_code=exc.broker_error_code,
            )

        if self._lifecycle_store is not None:
            self._lifecycle_store.save(pending_cancel)
        self._audit_log.append(
            {
                "type": "order_cancel_requested",
                "timestamp": request.timestamp.isoformat(),
                "account_id": request.account_id,
                "client_order_id": request.client_order_id,
                "broker_order_id": request.broker_order_id,
                "instrument_id": request.instrument_id,
                "previous_status": lifecycle.status.value,
                "status": pending_cancel.status.value,
            }
        )
        return OrderCancellationResult(
            lifecycle=pending_cancel,
            cancellation_requested=True,
        )
