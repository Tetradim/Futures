from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from futures_bot.domain.enums import OrderSide, OrderType
from futures_bot.domain.orders import OrderIntent
from futures_bot.ports.audit import AuditLogPort


@dataclass(frozen=True)
class OrderActivityRecord:
    client_order_id: str
    broker_order_id: str
    instrument_id: str
    timestamp: datetime
    side: OrderSide
    quantity: int
    order_type: OrderType
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if not self.broker_order_id:
            raise ValueError("broker_order_id is required")
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")


@dataclass(frozen=True)
class OrderActivitySnapshot:
    used_client_order_ids: frozenset[str]
    recent_order_timestamps: tuple[datetime, ...]


class OrderActivityStorePort(Protocol):
    def load(self) -> tuple[OrderActivityRecord, ...]:
        """Load persisted broker-accepted order activity."""

    def append(self, record: OrderActivityRecord) -> None:
        """Persist one broker-accepted order activity record."""


class OrderActivityTracker:
    def __init__(
        self,
        audit_log: AuditLogPort,
        store: OrderActivityStorePort | None = None,
    ) -> None:
        self._audit_log = audit_log
        self._store = store
        self._records: dict[str, OrderActivityRecord] = {}
        if store is not None:
            for record in store.load():
                self._add_record(record)

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

        record = OrderActivityRecord(
            client_order_id=intent.client_order_id,
            broker_order_id=broker_order_id,
            instrument_id=intent.instrument_id,
            timestamp=timestamp,
            side=intent.side,
            quantity=intent.quantity,
            order_type=intent.order_type,
            limit_price=intent.limit_price,
        )
        if self._store is not None:
            self._store.append(record)
        self._add_record(record)
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

    def record_for(self, client_order_id: str) -> OrderActivityRecord | None:
        return self._records.get(client_order_id)

    def _add_record(self, record: OrderActivityRecord) -> None:
        if record.client_order_id in self._records:
            raise ValueError("client order ID was already recorded")
        self._records[record.client_order_id] = record
