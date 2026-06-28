from __future__ import annotations

import json

import pytest

from futures_bot.storage.audit import JsonlAuditLog


def test_append_creates_parent_directories_and_persists_json_lines(tmp_path):
    path = tmp_path / "audit" / "orders.jsonl"
    log = JsonlAuditLog(path)

    log.append({"type": "risk_decision", "approved": False, "reason": "daily_loss"})
    log.append({"type": "order_state", "state": "rejected", "client_order_id": "abc-123"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"type": "risk_decision", "approved": False, "reason": "daily_loss"},
        {"type": "order_state", "state": "rejected", "client_order_id": "abc-123"},
    ]


def test_append_captures_a_copy_of_event(tmp_path):
    path = tmp_path / "audit.jsonl"
    event = {"type": "risk_decision", "approved": True}
    log = JsonlAuditLog(path)

    log.append(event)
    event["approved"] = False

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "type": "risk_decision",
        "approved": True,
    }


def test_read_events_returns_immutable_event_snapshots(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)

    log.append({"type": "order_state", "state": "working"})

    events = log.read_events()
    assert events == ({"type": "order_state", "state": "working"},)

    with pytest.raises(TypeError):
        events[0]["state"] = "filled"


def test_append_rejects_non_json_serializable_events(tmp_path):
    log = JsonlAuditLog(tmp_path / "audit.jsonl")

    with pytest.raises(ValueError, match="audit event must be JSON serializable"):
        log.append({"type": "bad_event", "values": {1, 2, 3}})
