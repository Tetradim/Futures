from __future__ import annotations

import json

import pytest

from futures_bot.domain.order_lifecycle import OrderLifecycle, OrderLifecycleStatus


def _store_class():
    try:
        from futures_bot.storage.order_lifecycles import JsonlOrderLifecycleStore
    except ModuleNotFoundError:
        pytest.fail("expected JsonlOrderLifecycleStore to exist")

    return JsonlOrderLifecycleStore


def test_jsonl_order_lifecycle_store_loads_latest_lifecycle_by_client_order_id(tmp_path):
    store = _store_class()(tmp_path / "state" / "order_lifecycles.jsonl")
    working = OrderLifecycle.pending_submit("order-1").mark_working()
    partially_filled = working.record_fill(fill_quantity=2, order_quantity=5)

    store.save(working)
    store.save(partially_filled)

    assert store.load("order-1") == partially_filled
    lines = (tmp_path / "state" / "order_lifecycles.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {
            "client_order_id": "order-1",
            "filled_quantity": 0,
            "reject_reason": None,
            "status": "working",
        },
        {
            "client_order_id": "order-1",
            "filled_quantity": 2,
            "reject_reason": None,
            "status": "partially_filled",
        },
    ]


def test_jsonl_order_lifecycle_store_returns_none_for_missing_order(tmp_path):
    store = _store_class()(tmp_path / "order_lifecycles.jsonl")

    assert store.load("order-1") is None


def test_jsonl_order_lifecycle_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "order_lifecycles.jsonl"
    path.write_text('{"client_order_id":"order-1"}\n', encoding="utf-8")
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid order lifecycle record"):
        store.load("order-1")


def test_jsonl_order_lifecycle_store_persists_rejected_lifecycle(tmp_path):
    store = _store_class()(tmp_path / "order_lifecycles.jsonl")
    lifecycle = OrderLifecycle(
        client_order_id="order-1",
        status=OrderLifecycleStatus.REJECTED,
        filled_quantity=0,
        reject_reason="broker rejected order",
    )

    store.save(lifecycle)

    assert store.load("order-1") == lifecycle
