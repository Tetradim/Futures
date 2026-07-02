from datetime import datetime, timezone
import json
from decimal import Decimal

import pytest

from sentinel_iron.application.margin_schedules import MarginScheduleEntry


EXPIRES = datetime(2026, 6, 29, 16, 45, tzinfo=timezone.utc)


def _store_class():
    try:
        from sentinel_iron.storage.margin_schedules import JsonMarginScheduleStore
    except ModuleNotFoundError:
        pytest.fail("expected JsonMarginScheduleStore to exist")

    return JsonMarginScheduleStore


def test_json_margin_schedule_store_loads_schedule_mapping(tmp_path):
    path = tmp_path / "state" / "margin_schedules.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            [
                {
                    "expires_at": "2026-06-29T16:45:00+00:00",
                    "initial_margin_per_contract": "12000",
                    "instrument_id": "ES-202609-CME",
                    "maintenance_margin_per_contract": "10000",
                    "source": "FCM daily margin schedule 2026-06-28",
                }
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    assert store.load() == {
        "ES-202609-CME": MarginScheduleEntry(
            instrument_id="ES-202609-CME",
            initial_margin_per_contract=Decimal("12000"),
            maintenance_margin_per_contract=Decimal("10000"),
            source="FCM daily margin schedule 2026-06-28",
            expires_at=EXPIRES,
        )
    }


def test_json_margin_schedule_store_saves_entries_in_stable_order(tmp_path):
    path = tmp_path / "state" / "margin_schedules.json"
    store = _store_class()(path)

    store.save(
        {
            "NQ-202609-CME": MarginScheduleEntry(
                instrument_id="NQ-202609-CME",
                initial_margin_per_contract=Decimal("18000"),
                maintenance_margin_per_contract=Decimal("15000"),
                source="FCM daily margin schedule 2026-06-28",
                expires_at=EXPIRES,
            ),
            "ES-202609-CME": MarginScheduleEntry(
                instrument_id="ES-202609-CME",
                initial_margin_per_contract=Decimal("12000"),
                maintenance_margin_per_contract=Decimal("10000"),
                source="FCM daily margin schedule 2026-06-28",
                expires_at=EXPIRES,
            ),
        }
    )

    assert json.loads(path.read_text(encoding="utf-8")) == [
        {
            "expires_at": "2026-06-29T16:45:00+00:00",
            "initial_margin_per_contract": "12000",
            "instrument_id": "ES-202609-CME",
            "maintenance_margin_per_contract": "10000",
            "source": "FCM daily margin schedule 2026-06-28",
        },
        {
            "expires_at": "2026-06-29T16:45:00+00:00",
            "initial_margin_per_contract": "18000",
            "instrument_id": "NQ-202609-CME",
            "maintenance_margin_per_contract": "15000",
            "source": "FCM daily margin schedule 2026-06-28",
        },
    ]
    assert store.load()["ES-202609-CME"].initial_margin_per_contract == Decimal("12000")


def test_json_margin_schedule_store_rejects_missing_file(tmp_path):
    store = _store_class()(tmp_path / "margin_schedules.json")

    with pytest.raises(ValueError, match="margin schedule file does not exist"):
        store.load()


def test_json_margin_schedule_store_rejects_duplicate_instruments(tmp_path):
    path = tmp_path / "margin_schedules.json"
    path.write_text(
        json.dumps(
            [
                {
                    "expires_at": "2026-06-29T16:45:00+00:00",
                    "initial_margin_per_contract": "12000",
                    "instrument_id": "ES-202609-CME",
                    "maintenance_margin_per_contract": "10000",
                    "source": "source-a",
                },
                {
                    "expires_at": "2026-06-29T16:45:00+00:00",
                    "initial_margin_per_contract": "13000",
                    "instrument_id": "ES-202609-CME",
                    "maintenance_margin_per_contract": "11000",
                    "source": "source-b",
                },
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    with pytest.raises(ValueError, match="duplicate margin schedule"):
        store.load()


def test_json_margin_schedule_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "margin_schedules.json"
    path.write_text('[{"instrument_id":"ES-202609-CME"}]', encoding="utf-8")
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid margin schedule record"):
        store.load()
