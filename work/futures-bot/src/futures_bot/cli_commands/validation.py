from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from futures_bot.application.kill_switch import KillSwitchService
from futures_bot.application.margin_estimates import MarginEstimateUnavailable
from futures_bot.application.margin_schedules import MarginScheduleProvider
from futures_bot.storage.audit import JsonlAuditLog
from futures_bot.storage.instruments import JsonInstrumentStore
from futures_bot.storage.kill_switch import JsonKillSwitchStore
from futures_bot.storage.margin_schedules import JsonMarginScheduleStore


def kill_switch(
    command: str | None,
    state_file_path: str,
    audit_log_path: str,
    reason: str | None,
) -> int:
    if command is None:
        print("kill-switch requires a subcommand: status, activate, or clear", file=sys.stderr)
        return 2

    service = KillSwitchService(
        store=JsonKillSwitchStore(Path(state_file_path)),
        audit_log=JsonlAuditLog(Path(audit_log_path)),
    )
    try:
        if command == "status":
            state = service.status()
        elif command == "activate":
            state = service.activate(reason=reason or "", timestamp=datetime.now(timezone.utc))
        elif command == "clear":
            state = service.clear(timestamp=datetime.now(timezone.utc))
        else:
            print(f"unsupported kill-switch command: {command}", file=sys.stderr)
            return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if state.active:
        print(f"kill switch active: reason={state.reason}")
    else:
        print("kill switch inactive")
    return 0


def margin_schedules(command: str | None, schedule_file_path: str) -> int:
    if command is None:
        print("margin-schedules requires a subcommand: validate", file=sys.stderr)
        return 2
    if command != "validate":
        print(f"unsupported margin-schedules command: {command}", file=sys.stderr)
        return 2

    try:
        entries = JsonMarginScheduleStore(Path(schedule_file_path)).load()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        MarginScheduleProvider(
            entries=entries,
            clock=lambda: datetime.now(timezone.utc),
        ).validate()
    except MarginEstimateUnavailable as exc:
        print(exc.reason, file=sys.stderr)
        return 1

    print(f"margin schedules valid: entries={len(entries)}")
    return 0


def instrument_catalog(
    command: str | None,
    catalog_file_path: str,
    trading_day_value: str | None,
) -> int:
    if command is None:
        print("instrument-catalog requires a subcommand: validate", file=sys.stderr)
        return 2
    if command != "validate":
        print(f"unsupported instrument-catalog command: {command}", file=sys.stderr)
        return 2

    try:
        instruments = JsonInstrumentStore(Path(catalog_file_path)).load()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if trading_day_value is not None:
        try:
            trading_day = date.fromisoformat(trading_day_value)
        except ValueError:
            print("trading-day must be YYYY-MM-DD", file=sys.stderr)
            return 2

        non_tradable = sorted(
            instrument.instrument_id
            for instrument in instruments.values()
            if not instrument.can_trade_on(trading_day)
        )
        if non_tradable:
            print(
                "instrument catalog contains non-tradable contracts for "
                f"{trading_day.isoformat()}: {', '.join(non_tradable)}",
                file=sys.stderr,
            )
            return 1

    print(f"instrument catalog valid: entries={len(instruments)}")
    return 0
