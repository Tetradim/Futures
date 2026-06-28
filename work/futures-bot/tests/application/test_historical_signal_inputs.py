from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from futures_bot.application.market_data import MarketDataHistoryService
from futures_bot.ports.audit import InMemoryAuditLog
from futures_bot.ports.market_data import HistoricalBar, MarketDataError


NOW = datetime(2026, 6, 28, 20, 30, tzinfo=timezone.utc)


class RecordingHistoricalProvider:
    def __init__(self, bars_by_instrument: dict[str, tuple[HistoricalBar, ...]]) -> None:
        self.bars_by_instrument = bars_by_instrument
        self.requests: list[tuple[str, date, date]] = []

    def get_daily_bars(
        self,
        instrument_id: str,
        start_day: date,
        end_day: date,
    ) -> tuple[HistoricalBar, ...]:
        self.requests.append((instrument_id, start_day, end_day))
        return self.bars_by_instrument.get(instrument_id, ())


class InMemoryHistoricalCache:
    def __init__(self, bars: tuple[HistoricalBar, ...] = ()) -> None:
        self.bars = bars
        self.saved: tuple[HistoricalBar, ...] | None = None

    def load(self) -> tuple[HistoricalBar, ...]:
        return self.bars

    def save(self, bars: tuple[HistoricalBar, ...]) -> None:
        self.saved = bars
        self.bars = bars


def test_historical_signal_input_builder_fetches_caches_and_builds_continuous_prices():
    from futures_bot.application.historical_signal_inputs import (
        HistoricalSignalInputBuilder,
        HistoricalSignalSegment,
    )

    provider = RecordingHistoricalProvider(
        {
            "ES-202609-CME": (
                _bar("ES-202609-CME", date(2026, 9, 13), "100"),
                _bar("ES-202609-CME", date(2026, 9, 14), "101"),
            ),
            "ES-202612-CME": (
                _bar("ES-202612-CME", date(2026, 9, 14), "110"),
                _bar("ES-202612-CME", date(2026, 9, 15), "111"),
            ),
        }
    )
    cache = InMemoryHistoricalCache(
        bars=(_bar("NQ-202609-CME", date(2026, 9, 13), "200"),)
    )
    builder = HistoricalSignalInputBuilder(
        history_service=MarketDataHistoryService(
            provider=provider,
            audit_log=InMemoryAuditLog(),
        ),
        cache=cache,
    )

    prices = builder.fetch_continuous_prices(
        provider_name="tradestation",
        segments=(
            HistoricalSignalSegment("ES-202609-CME", date(2026, 9, 13), date(2026, 9, 14)),
            HistoricalSignalSegment("ES-202612-CME", date(2026, 9, 14), date(2026, 9, 15)),
        ),
        timestamp=NOW,
    )

    assert provider.requests == [
        ("ES-202609-CME", date(2026, 9, 13), date(2026, 9, 14)),
        ("ES-202612-CME", date(2026, 9, 14), date(2026, 9, 15)),
    ]
    assert [(point.day, point.close) for point in prices] == [
        (date(2026, 9, 13), Decimal("109")),
        (date(2026, 9, 14), Decimal("110")),
        (date(2026, 9, 15), Decimal("111")),
    ]
    assert cache.saved == (
        _bar("ES-202609-CME", date(2026, 9, 13), "100"),
        _bar("ES-202609-CME", date(2026, 9, 14), "101"),
        _bar("ES-202612-CME", date(2026, 9, 14), "110"),
        _bar("ES-202612-CME", date(2026, 9, 15), "111"),
        _bar("NQ-202609-CME", date(2026, 9, 13), "200"),
    )


def test_historical_signal_input_builder_fails_when_segment_history_is_missing():
    from futures_bot.application.historical_signal_inputs import (
        HistoricalSignalInputBuilder,
        HistoricalSignalSegment,
    )

    builder = HistoricalSignalInputBuilder(
        history_service=MarketDataHistoryService(
            provider=RecordingHistoricalProvider({}),
            audit_log=InMemoryAuditLog(),
        ),
        cache=InMemoryHistoricalCache(),
    )

    with pytest.raises(MarketDataError, match="historical data provider returned no bars"):
        builder.fetch_continuous_prices(
            provider_name="tradestation",
            segments=(
                HistoricalSignalSegment("ES-202609-CME", date(2026, 9, 13), date(2026, 9, 14)),
            ),
            timestamp=NOW,
        )


def _bar(instrument_id: str, day: date, close: str) -> HistoricalBar:
    close_value = Decimal(close)
    return HistoricalBar(
        instrument_id=instrument_id,
        day=day,
        open=close_value - Decimal("1"),
        high=close_value + Decimal("1"),
        low=close_value - Decimal("2"),
        close=close_value,
        volume=1000,
    )
