from datetime import date
from decimal import Decimal
import json

import pytest

from sentinel_iron.ports.market_data import HistoricalBar


def _store_class():
    try:
        from sentinel_iron.storage.historical_bars import JsonHistoricalBarStore
    except ModuleNotFoundError:
        pytest.fail("expected JsonHistoricalBarStore to exist")

    return JsonHistoricalBarStore


def test_json_historical_bar_store_loads_bars_in_stable_order(tmp_path):
    path = tmp_path / "state" / "historical_bars.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            [
                _record("NQ-202609-CME", "2026-09-13", "19000", volume=None),
                _record("ES-202609-CME", "2026-09-14", "5010", volume=23456),
                _record("ES-202609-CME", "2026-09-13", "5000", volume=12345),
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    assert store.load() == (
        _bar("ES-202609-CME", date(2026, 9, 13), "5000", 12345),
        _bar("ES-202609-CME", date(2026, 9, 14), "5010", 23456),
        _bar("NQ-202609-CME", date(2026, 9, 13), "19000", None),
    )


def test_json_historical_bar_store_saves_bars_in_stable_order(tmp_path):
    path = tmp_path / "state" / "historical_bars.json"
    store = _store_class()(path)

    store.save(
        (
            _bar("NQ-202609-CME", date(2026, 9, 13), "19000", None),
            _bar("ES-202609-CME", date(2026, 9, 14), "5010", 23456),
            _bar("ES-202609-CME", date(2026, 9, 13), "5000", 12345),
        )
    )

    assert json.loads(path.read_text(encoding="utf-8")) == [
        _record("ES-202609-CME", "2026-09-13", "5000", volume=12345),
        _record("ES-202609-CME", "2026-09-14", "5010", volume=23456),
        _record("NQ-202609-CME", "2026-09-13", "19000", volume=None),
    ]


def test_json_historical_bar_store_loads_inclusive_range(tmp_path):
    path = tmp_path / "historical_bars.json"
    path.write_text(
        json.dumps(
            [
                _record("ES-202609-CME", "2026-09-12", "4990", volume=9000),
                _record("ES-202609-CME", "2026-09-13", "5000", volume=12345),
                _record("ES-202609-CME", "2026-09-14", "5010", volume=23456),
                _record("NQ-202609-CME", "2026-09-13", "19000", volume=None),
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    assert store.load_range("ES-202609-CME", date(2026, 9, 13), date(2026, 9, 14)) == (
        _bar("ES-202609-CME", date(2026, 9, 13), "5000", 12345),
        _bar("ES-202609-CME", date(2026, 9, 14), "5010", 23456),
    )


def test_json_historical_bar_store_rejects_missing_file(tmp_path):
    store = _store_class()(tmp_path / "historical_bars.json")

    with pytest.raises(ValueError, match="historical bar file does not exist"):
        store.load()


def test_json_historical_bar_store_rejects_duplicate_instrument_days(tmp_path):
    path = tmp_path / "historical_bars.json"
    path.write_text(
        json.dumps(
            [
                _record("ES-202609-CME", "2026-09-13", "5000", volume=12345),
                _record("ES-202609-CME", "2026-09-13", "5001", volume=12346),
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    with pytest.raises(ValueError, match="duplicate historical bar"):
        store.load()


def test_json_historical_bar_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "historical_bars.json"
    path.write_text('[{"instrument_id":"ES-202609-CME"}]', encoding="utf-8")
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid historical bar record"):
        store.load()


def test_json_historical_bar_store_rejects_fractional_volume(tmp_path):
    path = tmp_path / "historical_bars.json"
    path.write_text(
        json.dumps([_record("ES-202609-CME", "2026-09-13", "5000", volume="12345.5")]),
        encoding="utf-8",
    )
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid historical bar record"):
        store.load()


def _bar(
    instrument_id: str,
    day: date,
    close: str,
    volume: int | None,
) -> HistoricalBar:
    close_value = Decimal(close)
    return HistoricalBar(
        instrument_id=instrument_id,
        day=day,
        open=close_value - Decimal("1"),
        high=close_value + Decimal("1"),
        low=close_value - Decimal("2"),
        close=close_value,
        volume=volume,
    )


def _record(
    instrument_id: str,
    day: str,
    close: str,
    *,
    volume: int | None,
) -> dict[str, object]:
    close_value = Decimal(close)
    return {
        "close": str(close_value),
        "day": day,
        "high": str(close_value + Decimal("1")),
        "instrument_id": instrument_id,
        "low": str(close_value - Decimal("2")),
        "open": str(close_value - Decimal("1")),
        "volume": volume,
    }
