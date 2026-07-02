from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from sentinel_iron.market.ohlcv import decode_optional_integral_int
from sentinel_iron.ports.market_data import HistoricalBar


class JsonHistoricalBarStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> tuple[HistoricalBar, ...]:
        if not self.path.exists():
            raise ValueError("historical bar file does not exist")

        try:
            raw_value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid historical bar state") from exc

        if not isinstance(raw_value, list):
            raise ValueError("invalid historical bar state")

        bars = tuple(self._decode_bar(record_value) for record_value in raw_value)
        return self._sort_and_validate_unique(bars)

    def load_range(
        self,
        instrument_id: str,
        start_day: date,
        end_day: date,
    ) -> tuple[HistoricalBar, ...]:
        if not instrument_id:
            raise ValueError("instrument_id is required")
        if start_day > end_day:
            raise ValueError("start_day cannot be after end_day")

        return tuple(
            bar
            for bar in self.load()
            if bar.instrument_id == instrument_id and start_day <= bar.day <= end_day
        )

    def save(self, bars: tuple[HistoricalBar, ...]) -> None:
        payload = [
            self._encode_bar(bar)
            for bar in self._sort_and_validate_unique(tuple(bars))
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )

    def _encode_bar(self, bar: HistoricalBar) -> Mapping[str, object]:
        return {
            "close": str(bar.close),
            "day": bar.day.isoformat(),
            "high": str(bar.high),
            "instrument_id": bar.instrument_id,
            "low": str(bar.low),
            "open": str(bar.open),
            "volume": bar.volume,
        }

    def _decode_bar(self, value: object) -> HistoricalBar:
        if not isinstance(value, dict):
            raise ValueError("invalid historical bar record")

        try:
            instrument_id = value["instrument_id"]
            day = value["day"]
            open_price = value["open"]
            high = value["high"]
            low = value["low"]
            close = value["close"]
            volume = value["volume"]
            if not isinstance(instrument_id, str):
                raise TypeError
            if not isinstance(day, str):
                raise TypeError
            bar = HistoricalBar(
                instrument_id=instrument_id,
                day=date.fromisoformat(day),
                open=Decimal(str(open_price)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=self._decode_volume(volume),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid historical bar record") from exc

        return bar

    def _decode_volume(self, value: object) -> int | None:
        return decode_optional_integral_int(value, "volume")

    def _sort_and_validate_unique(
        self,
        bars: tuple[HistoricalBar, ...],
    ) -> tuple[HistoricalBar, ...]:
        ordered_bars = tuple(sorted(bars, key=lambda bar: (bar.instrument_id, bar.day)))
        seen_keys: set[tuple[str, date]] = set()
        for bar in ordered_bars:
            key = (bar.instrument_id, bar.day)
            if key in seen_keys:
                raise ValueError(
                    f"duplicate historical bar: {bar.instrument_id} {bar.day.isoformat()}"
                )
            seen_keys.add(key)
        return ordered_bars
