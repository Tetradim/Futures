from __future__ import annotations

from futures_bot.domain.order_lifecycle import OrderLifecycle
from futures_bot.ports.audit import AuditLogPort
from futures_bot.ports.broker import BrokerOrderUpdate, BrokerOrderUpdateType


class OrderUpdateService:
    def __init__(self, audit_log: AuditLogPort) -> None:
        self._audit_log = audit_log

    def apply(
        self,
        lifecycle: OrderLifecycle,
        update: BrokerOrderUpdate,
        order_quantity: int,
    ) -> OrderLifecycle:
        if order_quantity <= 0:
            raise ValueError("order_quantity must be positive")
        if update.client_order_id != lifecycle.client_order_id:
            raise ValueError("broker update client_order_id does not match lifecycle")

        if update.update_type == BrokerOrderUpdateType.WORKING:
            updated = lifecycle.mark_working()
        elif update.update_type == BrokerOrderUpdateType.FILL:
            updated = lifecycle.record_fill(update.fill_quantity, order_quantity)
        elif update.update_type == BrokerOrderUpdateType.CANCELED:
            updated = lifecycle.mark_canceled()
        elif update.update_type == BrokerOrderUpdateType.REJECTED:
            updated = lifecycle.mark_rejected(update.reject_reason or "")
        else:
            raise ValueError(f"unsupported broker update type: {update.update_type}")

        self._audit_log.append(
            {
                "type": "order_update_applied",
                "timestamp": update.timestamp.isoformat(),
                "account_id": update.account_id,
                "client_order_id": update.client_order_id,
                "broker_order_id": update.broker_order_id,
                "instrument_id": update.instrument_id,
                "update_type": update.update_type.value,
                "status": updated.status.value,
                "fill_quantity": update.fill_quantity,
                "filled_quantity": updated.filled_quantity,
                "reject_reason": updated.reject_reason,
                "broker_error_code": update.broker_error_code,
            }
        )
        return updated
