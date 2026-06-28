from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from futures_bot.application.market_data import (
    MarketDataHistoryRequest,
    MarketDataHistoryService,
)
from futures_bot.market.continuous import (
    ContractPriceSeries,
    build_back_adjusted_continuous_series,
)
from futures_bot.ports.market_data import HistoricalBar, MarketDataError
from futures_bot.strategies.trend_following import PricePoint


class HistoricalBarCachePort(Protocol):
    def load(self) -> tuple[HistoricalBar, ...]:
        """Load cached historical bars."""

    def save(self, bars: tuple[HistoricalBar, ...]) -> None:
        """Persist cached historical bars."""


@dataclass(frozen=True)
class HistoricalSignalSegment:
    instrument_id: str
    start_day: date
    end_day: date

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.start_day > self.end_day:
            raise ValueError("start_day cannot be after end_day")


class HistoricalSignalInputBuilder:
    def __init__(
        self,
        history_service: MarketDataHistoryService,
        cache: HistoricalBarCachePort,
    ) -> None:
        self._history_service = history_service
        self._cache = cache

    def fetch_continuous_prices(
        self,
        provider_name: str,
        segments: tuple[HistoricalSignalSegment, ...],
        timestamp: datetime,
    ) -> tuple[PricePoint, ...]:
        if not provider_name:
            raise ValueError("provider_name is required")
        if not segments:
            raise ValueError("historical signal segments are required")

        fetched_segments: list[tuple[HistoricalBar, ...]] = []
        fetched_bars: list[HistoricalBar] = []
        for segment in segments:
            result = self._history_service.get_daily_bars(
                MarketDataHistoryRequest(
                    provider_name=provider_name,
                    instrument_id=segment.instrument_id,
                    start_day=segment.start_day,
                    end_day=segment.end_day,
                    timestamp=timestamp,
                )
            )
            if not result.received:
                detail = result.detail or result.reason or "historical data was rejected"
                raise MarketDataError(detail, result.reason)

            fetched_segments.append(result.bars)
            fetched_bars.extend(result.bars)

        self._cache_fetched_bars(tuple(fetched_bars))
        contract_segments = tuple(
            ContractPriceSeries(
                instrument_id=segment.instrument_id,
                prices=_price_points(segment_bars),
            )
            for segment, segment_bars in zip(segments, fetched_segments, strict=True)
        )
        return build_back_adjusted_continuous_series(contract_segments)

    def _cache_fetched_bars(self, fetched_bars: tuple[HistoricalBar, ...]) -> None:
        existing_bars = _load_existing_cache(self._cache)
        merged_bars = _merge_bars(existing_bars + fetched_bars)
        self._cache.save(merged_bars)


def _load_existing_cache(cache: HistoricalBarCachePort) -> tuple[HistoricalBar, ...]:
    try:
        return cache.load()
    except ValueError as exc:
        if str(exc) == "historical bar file does not exist":
            return ()
        raise


def _merge_bars(bars: tuple[HistoricalBar, ...]) -> tuple[HistoricalBar, ...]:
    merged: dict[tuple[str, date], HistoricalBar] = {}
    for bar in bars:
        merged[(bar.instrument_id, bar.day)] = bar
    return tuple(merged[key] for key in sorted(merged))


def _price_points(bars: tuple[HistoricalBar, ...]) -> tuple[PricePoint, ...]:
    return tuple(
        PricePoint(day=bar.day, close=bar.close)
        for bar in sorted(bars, key=lambda item: item.day)
    )
