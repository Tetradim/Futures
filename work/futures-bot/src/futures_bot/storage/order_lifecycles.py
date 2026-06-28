from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from futures_bot.domain.order_lifecycle import OrderLifecycle, OrderLifecycleStatus


class JsonlOrderLifecycleStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self, client_order_id: str) -> OrderLifecycle | None:
        if not client_order_id:
            raise ValueError("client_order_id is required")
        if not self.path.exists():
            return None

        latest: OrderLifecycle | None = None
        with self.path.open(encoding="utf-8") as state_file:
            for line in state_file:
                if not line.strip():
                    continue
                lifecycle = self._decode_record(json.loads(line))
                if lifecycle.client_order_id == client_order_id:
                    latest = lifecycle
        return latest

    def save(self, lifecycle: OrderLifecycle) -> None:
        line = json.dumps(
            self._encode_record(lifecycle),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as state_file:
            state_file.write(f"{line}\n")

    def _encode_record(self, lifecycle: OrderLifecycle) -> Mapping[str, object]:
        if not lifecycle.client_order_id:
            raise ValueError("client_order_id is required")
        if not isinstance(lifecycle.status, OrderLifecycleStatus):
            raise ValueError("status is required")
        if lifecycle.filled_quantity < 0:
            raise ValueError("filled_quantity cannot be negative")
        if lifecycle.reject_reason is not None and not lifecycle.reject_reason:
            raise ValueError("reject_reason cannot be empty")

        return {
            "client_order_id": lifecycle.client_order_id,
            "status": lifecycle.status.value,
            "filled_quantity": lifecycle.filled_quantity,
            "reject_reason": lifecycle.reject_reason,
        }

    def _decode_record(self, value: object) -> OrderLifecycle:
        if not isinstance(value, dict):
            raise ValueError("invalid order lifecycle record")

        try:
            client_order_id = value["client_order_id"]
            status_value = value["status"]
            filled_quantity = value["filled_quantity"]
            reject_reason = value["reject_reason"]
            if not isinstance(client_order_id, str):
                raise TypeError
            if not isinstance(status_value, str):
                raise TypeError
            if not isinstance(filled_quantity, int):
                raise TypeError
            if reject_reason is not None and not isinstance(reject_reason, str):
                raise TypeError
            lifecycle = OrderLifecycle(
                client_order_id=client_order_id,
                status=OrderLifecycleStatus(status_value),
                filled_quantity=filled_quantity,
                reject_reason=reject_reason,
            )
            self._encode_record(lifecycle)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid order lifecycle record") from exc

        return lifecycle
