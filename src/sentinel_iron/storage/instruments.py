from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from sentinel_iron.domain.enums import SettlementType
from sentinel_iron.domain.instruments import ContractSpec, FuturesInstrument, TradingCalendar


class JsonInstrumentStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Mapping[str, FuturesInstrument]:
        if not self.path.exists():
            raise ValueError("instrument catalog file does not exist")

        try:
            raw_value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid instrument catalog state") from exc

        if not isinstance(raw_value, list):
            raise ValueError("invalid instrument catalog state")

        instruments: dict[str, FuturesInstrument] = {}
        for record_value in raw_value:
            instrument = self._decode_instrument(record_value)
            if instrument.instrument_id in instruments:
                raise ValueError(f"duplicate instrument: {instrument.instrument_id}")
            instruments[instrument.instrument_id] = instrument
        return instruments

    def save(self, instruments: Mapping[str, FuturesInstrument]) -> None:
        payload = [
            self._encode_instrument(instrument)
            for instrument in sorted(
                instruments.values(), key=lambda item: item.instrument_id
            )
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )

    def _encode_instrument(self, instrument: FuturesInstrument) -> Mapping[str, object]:
        return {
            "calendar": {
                "first_notice_date": self._encode_optional_date(
                    instrument.calendar.first_notice_date
                ),
                "last_safe_trade_date": instrument.calendar.last_safe_trade_date.isoformat(),
                "last_trade_date": instrument.calendar.last_trade_date.isoformat(),
            },
            "instrument_id": instrument.instrument_id,
            "spec": {
                "contract_month": instrument.spec.contract_month,
                "currency": instrument.spec.currency,
                "exchange": instrument.spec.exchange,
                "multiplier": str(instrument.spec.multiplier),
                "settlement_type": instrument.spec.settlement_type.value,
                "symbol": instrument.spec.symbol,
                "tick_size": str(instrument.spec.tick_size),
            },
        }

    def _decode_instrument(self, value: object) -> FuturesInstrument:
        if not isinstance(value, dict):
            raise ValueError("invalid instrument record")

        try:
            instrument_id = value["instrument_id"]
            spec_value = value["spec"]
            calendar_value = value["calendar"]
            if not isinstance(instrument_id, str):
                raise TypeError
            if not isinstance(spec_value, dict):
                raise TypeError
            if not isinstance(calendar_value, dict):
                raise TypeError

            instrument = FuturesInstrument(
                instrument_id=instrument_id,
                spec=self._decode_spec(spec_value),
                calendar=self._decode_calendar(calendar_value),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid instrument record") from exc

        return instrument

    def _decode_spec(self, value: Mapping[str, object]) -> ContractSpec:
        symbol = value["symbol"]
        exchange = value["exchange"]
        contract_month = value["contract_month"]
        multiplier = value["multiplier"]
        tick_size = value["tick_size"]
        currency = value["currency"]
        settlement_type = value["settlement_type"]
        if not isinstance(symbol, str):
            raise TypeError
        if not isinstance(exchange, str):
            raise TypeError
        if not isinstance(contract_month, str):
            raise TypeError
        if not isinstance(currency, str):
            raise TypeError
        if not isinstance(settlement_type, str):
            raise TypeError

        return ContractSpec(
            symbol=symbol,
            exchange=exchange,
            contract_month=contract_month,
            multiplier=Decimal(str(multiplier)),
            tick_size=Decimal(str(tick_size)),
            currency=currency,
            settlement_type=SettlementType(settlement_type),
        )

    def _decode_calendar(self, value: Mapping[str, object]) -> TradingCalendar:
        first_notice_date = value["first_notice_date"]
        last_trade_date = value["last_trade_date"]
        last_safe_trade_date = value["last_safe_trade_date"]
        if first_notice_date is not None and not isinstance(first_notice_date, str):
            raise TypeError
        if not isinstance(last_trade_date, str):
            raise TypeError
        if not isinstance(last_safe_trade_date, str):
            raise TypeError

        return TradingCalendar(
            first_notice_date=self._decode_optional_date(first_notice_date),
            last_trade_date=date.fromisoformat(last_trade_date),
            last_safe_trade_date=date.fromisoformat(last_safe_trade_date),
        )

    def _encode_optional_date(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    def _decode_optional_date(self, value: str | None) -> date | None:
        if value is None:
            return None
        return date.fromisoformat(value)
