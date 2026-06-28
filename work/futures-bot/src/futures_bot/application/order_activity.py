from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from futures_bot.domain.orders import OrderIntent
from futures_bot.ports.audit import AuditLogPort


@dataclass(frozen=True)
class OrderActivityRecord:
    client_order_id: str
    broker_order_id: str
    instrument_id: str
    timestamp: datetime


@dataclass(frozen=True)
class OrderActivitySnapshot:
    used_client_order_ids: frozenset[str]
    recent_order_timestamps: tuple[datetime, ...]


class OrderActivityTracker:
    def __init__(self, audit_log: AuditLogPort) -> None:
        self._audit_log = audit_log
        self._records: dict[str, OrderActivityRecord] = {}

    def record_submission(
        self,
        intent: OrderIntent,
        timestamp: datetime,
        broker_order_id: str,
    ) -> None:
        if not broker_order_id:
            raise ValueError("broker_order_id is required")
        if intent.client_order_id in self._records:
            raise ValueError("client order ID was already recorded")

        self._records[intent.client_order_id] = OrderActivityRecord(
            client_order_id=intent.client_order_id,
            broker_order_id=broker_order_id,
            instrument_id=intent.instrument_id,
            timestamp=timestamp,
        )
        self._audit_log.append(
            {
                "type": "order_activity_recorded",
                "timestamp": timestamp.isoformat(),
                "client_order_id": intent.client_order_id,
                "broker_order_id": broker_order_id,
                "instrument_id": intent.instrument_id,
                "side": intent.side.value,
                "quantity": intent.quantity,
                "order_type": intent.order_type.value,
                "limit_price": str(intent.limit_price) if intent.limit_price is not None else None,
            }
        )

    def snapshot(self, now: datetime, recent_order_window: timedelta) -> OrderActivitySnapshot:
        if recent_order_window <= timedelta(0):
            raise ValueError("recent_order_window must be positive")

        recent_timestamps = tuple(
            record.timestamp
            for record in sorted(self._records.values(), key=lambda record: record.timestamp)
            if now - record.timestamp <= recent_order_window
        )
        return OrderActivitySnapshot(
            used_client_order_ids=frozenset(self._records),
            recent_order_timestamps=recent_timestamps,
        )
