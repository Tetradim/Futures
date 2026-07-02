from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


class JsonlAuditLog:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, event: Mapping[str, object]) -> None:
        snapshot = dict(event)
        try:
            line = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("audit event must be JSON serializable") from exc

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(f"{line}\n")

    def read_events(self) -> tuple[Mapping[str, object], ...]:
        events: list[Mapping[str, object]] = []
        with self.path.open(encoding="utf-8") as audit_file:
            for line in audit_file:
                if line.strip():
                    events.append(MappingProxyType(json.loads(line)))
        return tuple(events)
