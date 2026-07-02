from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from sentinel_iron.application.margin_schedules import MarginScheduleEntry


class JsonMarginScheduleStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Mapping[str, MarginScheduleEntry]:
        if not self.path.exists():
            raise ValueError("margin schedule file does not exist")

        try:
            raw_value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid margin schedule state") from exc

        if not isinstance(raw_value, list):
            raise ValueError("invalid margin schedule state")

        entries: dict[str, MarginScheduleEntry] = {}
        for record_value in raw_value:
            entry = self._decode_entry(record_value)
            if entry.instrument_id in entries:
                raise ValueError(f"duplicate margin schedule: {entry.instrument_id}")
            entries[entry.instrument_id] = entry
        return entries

    def save(self, entries: Mapping[str, MarginScheduleEntry]) -> None:
        payload = [
            self._encode_entry(entry)
            for entry in sorted(entries.values(), key=lambda item: item.instrument_id)
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )

    def _encode_entry(self, entry: MarginScheduleEntry) -> Mapping[str, object]:
        return {
            "expires_at": entry.expires_at.isoformat(),
            "initial_margin_per_contract": str(entry.initial_margin_per_contract),
            "instrument_id": entry.instrument_id,
            "maintenance_margin_per_contract": str(entry.maintenance_margin_per_contract),
            "source": entry.source,
        }

    def _decode_entry(self, value: object) -> MarginScheduleEntry:
        if not isinstance(value, dict):
            raise ValueError("invalid margin schedule record")

        try:
            instrument_id = value["instrument_id"]
            initial_margin_per_contract = value["initial_margin_per_contract"]
            maintenance_margin_per_contract = value["maintenance_margin_per_contract"]
            source = value["source"]
            expires_at = value["expires_at"]
            if not isinstance(instrument_id, str):
                raise TypeError
            if not isinstance(source, str):
                raise TypeError
            if not isinstance(expires_at, str):
                raise TypeError
            entry = MarginScheduleEntry(
                instrument_id=instrument_id,
                initial_margin_per_contract=Decimal(str(initial_margin_per_contract)),
                maintenance_margin_per_contract=Decimal(
                    str(maintenance_margin_per_contract)
                ),
                source=source,
                expires_at=self._decode_expires_at(expires_at),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid margin schedule record") from exc

        return entry

    def _decode_expires_at(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
