from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class OrderLifecycleStatus(StrEnum):
    PENDING_SUBMIT = "pending_submit"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PENDING_CANCEL = "pending_cancel"
    CANCELED = "canceled"
    REJECTED = "rejected"


TERMINAL_STATUSES = frozenset(
    {
        OrderLifecycleStatus.FILLED,
        OrderLifecycleStatus.CANCELED,
        OrderLifecycleStatus.REJECTED,
    }
)


@dataclass(frozen=True)
class OrderLifecycle:
    client_order_id: str
    status: OrderLifecycleStatus
    filled_quantity: int = 0
    reject_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if self.filled_quantity < 0:
            raise ValueError("filled_quantity cannot be negative")

    @classmethod
    def pending_submit(cls, client_order_id: str) -> OrderLifecycle:
        return cls(
            client_order_id=client_order_id,
            status=OrderLifecycleStatus.PENDING_SUBMIT,
        )

    def mark_working(self) -> OrderLifecycle:
        self._require_transition(OrderLifecycleStatus.WORKING, {OrderLifecycleStatus.PENDING_SUBMIT})
        return replace(self, status=OrderLifecycleStatus.WORKING)

    def record_fill(self, fill_quantity: int, order_quantity: int) -> OrderLifecycle:
        if fill_quantity <= 0:
            raise ValueError("fill_quantity must be positive")
        if order_quantity <= 0:
            raise ValueError("order_quantity must be positive")
        if self.status in TERMINAL_STATUSES:
            self._raise_invalid_transition(OrderLifecycleStatus.PARTIALLY_FILLED)
        if self.status not in {OrderLifecycleStatus.WORKING, OrderLifecycleStatus.PARTIALLY_FILLED}:
            self._raise_invalid_transition(OrderLifecycleStatus.PARTIALLY_FILLED)

        filled_quantity = self.filled_quantity + fill_quantity
        if filled_quantity > order_quantity:
            raise ValueError("filled quantity cannot exceed order quantity")

        status = (
            OrderLifecycleStatus.FILLED
            if filled_quantity == order_quantity
            else OrderLifecycleStatus.PARTIALLY_FILLED
        )
        return replace(self, status=status, filled_quantity=filled_quantity)

    def mark_pending_cancel(self) -> OrderLifecycle:
        self._require_transition(
            OrderLifecycleStatus.PENDING_CANCEL,
            {OrderLifecycleStatus.WORKING, OrderLifecycleStatus.PARTIALLY_FILLED},
        )
        return replace(self, status=OrderLifecycleStatus.PENDING_CANCEL)

    def mark_canceled(self) -> OrderLifecycle:
        self._require_transition(
            OrderLifecycleStatus.CANCELED,
            {OrderLifecycleStatus.PENDING_CANCEL},
        )
        return replace(self, status=OrderLifecycleStatus.CANCELED)

    def mark_rejected(self, reason: str) -> OrderLifecycle:
        if not reason:
            raise ValueError("reason is required")
        self._require_transition(
            OrderLifecycleStatus.REJECTED,
            {OrderLifecycleStatus.PENDING_SUBMIT, OrderLifecycleStatus.WORKING},
        )
        return replace(self, status=OrderLifecycleStatus.REJECTED, reject_reason=reason)

    def _require_transition(
        self,
        next_status: OrderLifecycleStatus,
        allowed_current_statuses: set[OrderLifecycleStatus],
    ) -> None:
        if self.status not in allowed_current_statuses:
            self._raise_invalid_transition(next_status)

    def _raise_invalid_transition(self, next_status: OrderLifecycleStatus) -> None:
        raise ValueError(f"cannot transition from {self.status.value} to {next_status.value}")
