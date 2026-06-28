from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from futures_bot.application.order_activity import OrderActivityRecord
from futures_bot.domain.enums import OrderSide, OrderType


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
        if record.timestamp.tzinfo is None or record.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if not isinstance(record.side, OrderSide):
            raise ValueError("side is required")
        if record.quantity <= 0:
            raise ValueError("quantity must be positive")
        if not isinstance(record.order_type, OrderType):
            raise ValueError("order_type is required")
        if record.order_type == OrderType.LIMIT and record.limit_price is None:
            raise ValueError("limit_price is required for limit orders")

        return {
            "client_order_id": record.client_order_id,
            "broker_order_id": record.broker_order_id,
            "instrument_id": record.instrument_id,
            "side": record.side.value,
            "quantity": record.quantity,
            "order_type": record.order_type.value,
            "limit_price": str(record.limit_price) if record.limit_price is not None else None,
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
            side_value = value["side"]
            quantity_value = value["quantity"]
            order_type_value = value["order_type"]
            limit_price_value = value["limit_price"]
            if not isinstance(client_order_id, str):
                raise TypeError
            if not isinstance(broker_order_id, str):
                raise TypeError
            if not isinstance(instrument_id, str):
                raise TypeError
            if not isinstance(timestamp_value, str):
                raise TypeError
            if not isinstance(side_value, str):
                raise TypeError
            if not isinstance(quantity_value, int):
                raise TypeError
            if not isinstance(order_type_value, str):
                raise TypeError
            if limit_price_value is not None and not isinstance(limit_price_value, str):
                raise TypeError
            limit_price = Decimal(limit_price_value) if limit_price_value is not None else None
            timestamp = datetime.fromisoformat(timestamp_value)
            record = OrderActivityRecord(
                client_order_id=client_order_id,
                broker_order_id=broker_order_id,
                instrument_id=instrument_id,
                timestamp=timestamp,
                side=OrderSide(side_value),
                quantity=quantity_value,
                order_type=OrderType(order_type_value),
                limit_price=limit_price,
            )
            self._encode_record(record)
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError("invalid order activity record") from exc

        return record
