from __future__ import annotations

from datetime import datetime, timedelta, timezone

from futures_bot.application.order_activity import OrderActivityRecord, OrderActivityTracker
from futures_bot.ports.audit import InMemoryAuditLog


NOW = datetime(2026, 6, 28, 15, 0, tzinfo=timezone.utc)


class MemoryOrderActivityStore:
    def __init__(self, records: tuple[OrderActivityRecord, ...]) -> None:
        self.loaded_records = records
        self.appended_records: list[OrderActivityRecord] = []

    def load(self) -> tuple[OrderActivityRecord, ...]:
        return self.loaded_records

    def append(self, record: OrderActivityRecord) -> None:
        self.appended_records.append(record)


def test_order_activity_tracker_hydrates_persisted_records_for_risk_inputs():
    store = MemoryOrderActivityStore(
        (
            OrderActivityRecord(
                client_order_id="order-1",
                broker_order_id="broker-123",
                instrument_id="ES-202609-CME",
                timestamp=NOW - timedelta(seconds=15),
            ),
        )
    )

    tracker = OrderActivityTracker(InMemoryAuditLog(), store=store)
    snapshot = tracker.snapshot(now=NOW, recent_order_window=timedelta(minutes=1))

    assert snapshot.used_client_order_ids == frozenset({"order-1"})
    assert snapshot.recent_order_timestamps == (NOW - timedelta(seconds=15),)

