from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sentinel_iron.application.margin_estimates import MarginEstimateUnavailable
from sentinel_iron.application.rebalance_risk_context import MarginEstimate
from sentinel_iron.domain.orders import BrokerOrder


@dataclass(frozen=True)
class MarginScheduleEntry:
    instrument_id: str
    initial_margin_per_contract: Decimal
    maintenance_margin_per_contract: Decimal
    source: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.initial_margin_per_contract <= 0:
            raise ValueError("initial_margin_per_contract must be positive")
        if self.maintenance_margin_per_contract <= 0:
            raise ValueError("maintenance_margin_per_contract must be positive")
        if not self.source:
            raise ValueError("source is required")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")


class MarginScheduleProvider:
    def __init__(
        self,
        entries: Mapping[str, MarginScheduleEntry],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._entries = dict(entries)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def estimate_order_margin(self, order: BrokerOrder) -> MarginEstimate:
        entry = self._entries.get(order.instrument_id)
        if entry is None:
            raise MarginEstimateUnavailable(
                f"margin schedule is required for {order.instrument_id}"
            )
        self._validate_entry(order.instrument_id, entry, self._clock())

        return MarginEstimate(
            initial_margin=entry.initial_margin_per_contract * order.quantity,
            maintenance_margin=entry.maintenance_margin_per_contract * order.quantity,
        )

    def validate(self) -> None:
        now = self._clock()
        for instrument_id, entry in self._entries.items():
            self._validate_entry(instrument_id, entry, now)

    def _validate_entry(
        self,
        instrument_id: str,
        entry: MarginScheduleEntry,
        now: datetime,
    ) -> None:
        if entry.instrument_id != instrument_id:
            raise MarginEstimateUnavailable(
                f"margin schedule instrument does not match {instrument_id}"
            )
        if now >= entry.expires_at:
            raise MarginEstimateUnavailable(
                f"margin schedule for {instrument_id} expired at "
                f"{entry.expires_at.isoformat()}"
            )
