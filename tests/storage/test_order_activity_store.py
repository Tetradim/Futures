from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from sentinel_iron.application.order_activity import OrderActivityRecord
from sentinel_iron.domain.enums import OrderSide, OrderType


NOW = datetime(2026, 6, 28, 14, 50, tzinfo=timezone.utc)


def _store_class():
    try:
        from sentinel_iron.storage.order_activity import JsonlOrderActivityStore
    except ModuleNotFoundError:
        pytest.fail("expected JsonlOrderActivityStore to exist")

    return JsonlOrderActivityStore


def _record(client_order_id: str = "order-1") -> OrderActivityRecord:
    return OrderActivityRecord(
        client_order_id=client_order_id,
        broker_order_id="broker-123",
        instrument_id="ES-202609-CME",
        timestamp=NOW,
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("5000.25"),
    )


def test_jsonl_order_activity_store_persists_and_reloads_records(tmp_path):
    store = _store_class()(tmp_path / "state" / "order_activity.jsonl")

    store.append(_record())
    loaded = store.load()

    assert loaded == (_record(),)
    assert json.loads((tmp_path / "state" / "order_activity.jsonl").read_text()) == {
        "broker_order_id": "broker-123",
        "client_order_id": "order-1",
        "instrument_id": "ES-202609-CME",
        "limit_price": "5000.25",
        "order_type": "limit",
        "quantity": 1,
        "side": "buy",
        "timestamp": "2026-06-28T14:50:00+00:00",
    }


def test_jsonl_order_activity_store_rejects_duplicate_client_order_ids(tmp_path):
    store = _store_class()(tmp_path / "order_activity.jsonl")

    store.append(_record("order-1"))

    with pytest.raises(ValueError, match="client order ID was already persisted"):
        store.append(_record("order-1"))


def test_jsonl_order_activity_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "order_activity.jsonl"
    path.write_text('{"client_order_id":"order-1"}\n', encoding="utf-8")
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid order activity record"):
        store.load()
