from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Mapping

from futures_bot.application.order_activity import OrderActivityRecord


class JsonlOrderActivityStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> tuple[OrderActivityRecord, ...]:
        if not self.path.exists():
            return ()

        records: list[OrderActivityRecord] = []
        used_client_order_ids: set[str] = set()
        with self.path.open(encoding="utf-8") as state_file:
            for line in state_file:
                if not line.strip():
                    continue
                record = self._decode_record(json.loads(line))
                if record.client_order_id in used_client_order_ids:
                    raise ValueError("client order ID was already persisted")
                used_client_order_ids.add(record.client_order_id)
                records.append(record)
        return tuple(records)

    def append(self, record: OrderActivityRecord) -> None:
        if record.client_order_id in {persisted.client_order_id for persisted in self.load()}:
            raise ValueError("client order ID was already persisted")

        line = json.dumps(
            self._encode_record(record),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as state_file:
            state_file.write(f"{line}\n")

    def _encode_record(self, record: OrderActivityRecord) -> Mapping[str, object]:
        if not record.client_order_id:
            raise ValueError("client_order_id is required")
        if not record.broker_order_id:
            raise ValueError("broker_order_id is required")
        if not record.instrument_id:
            raise ValueError("instrument_id is required")
        if record.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        return {
            "client_order_id": record.client_order_id,
            "broker_order_id": record.broker_order_id,
            "instrument_id": record.instrument_id,
            "timestamp": record.timestamp.isoformat(),
        }

    def _decode_record(self, value: object) -> OrderActivityRecord:
        if not isinstance(value, dict):
            raise ValueError("invalid order activity record")

        try:
            client_order_id = value["client_order_id"]
            broker_order_id = value["broker_order_id"]
            instrument_id = value["instrument_id"]
            timestamp_value = value["timestamp"]
            if not isinstance(client_order_id, str):
                raise TypeError
            if not isinstance(broker_order_id, str):
                raise TypeError
            if not isinstance(instrument_id, str):
                raise TypeError
            if not isinstance(timestamp_value, str):
                raise TypeError
            timestamp = datetime.fromisoformat(timestamp_value)
            record = OrderActivityRecord(
                client_order_id=client_order_id,
                broker_order_id=broker_order_id,
                instrument_id=instrument_id,
                timestamp=timestamp,
            )
            self._encode_record(record)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid order activity record") from exc

        return record
