from datetime import date
from decimal import Decimal
import json

import pytest

from sentinel_iron.domain.enums import SettlementType
from sentinel_iron.domain.instruments import ContractSpec, FuturesInstrument, TradingCalendar


def _store_class():
    try:
        from sentinel_iron.storage.instruments import JsonInstrumentStore
    except ModuleNotFoundError:
        pytest.fail("expected JsonInstrumentStore to exist")

    return JsonInstrumentStore


def test_json_instrument_store_loads_catalog_mapping(tmp_path):
    path = tmp_path / "state" / "instruments.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            [
                {
                    "calendar": {
                        "first_notice_date": None,
                        "last_safe_trade_date": "2026-09-14",
                        "last_trade_date": "2026-09-18",
                    },
                    "instrument_id": "ES-202609-CME",
                    "spec": {
                        "contract_month": "202609",
                        "currency": "USD",
                        "exchange": "CME",
                        "multiplier": "50",
                        "settlement_type": "cash",
                        "symbol": "ES",
                        "tick_size": "0.25",
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    assert store.load() == {
        "ES-202609-CME": FuturesInstrument(
            instrument_id="ES-202609-CME",
            spec=ContractSpec(
                symbol="ES",
                exchange="CME",
                contract_month="202609",
                multiplier=Decimal("50"),
                tick_size=Decimal("0.25"),
                currency="USD",
                settlement_type=SettlementType.CASH,
            ),
            calendar=TradingCalendar(
                first_notice_date=None,
                last_trade_date=date(2026, 9, 18),
                last_safe_trade_date=date(2026, 9, 14),
            ),
        )
    }


def test_json_instrument_store_saves_catalog_in_stable_order(tmp_path):
    path = tmp_path / "state" / "instruments.json"
    store = _store_class()(path)

    store.save(
        {
            "ZC-202612-CBOT": FuturesInstrument(
                instrument_id="ZC-202612-CBOT",
                spec=ContractSpec(
                    symbol="ZC",
                    exchange="CBOT",
                    contract_month="202612",
                    multiplier=Decimal("5000"),
                    tick_size=Decimal("0.25"),
                    currency="USD",
                    settlement_type=SettlementType.PHYSICAL,
                ),
                calendar=TradingCalendar(
                    first_notice_date=date(2026, 11, 30),
                    last_trade_date=date(2026, 12, 14),
                    last_safe_trade_date=date(2026, 11, 27),
                ),
            ),
            "ES-202609-CME": FuturesInstrument(
                instrument_id="ES-202609-CME",
                spec=ContractSpec(
                    symbol="ES",
                    exchange="CME",
                    contract_month="202609",
                    multiplier=Decimal("50"),
                    tick_size=Decimal("0.25"),
                    currency="USD",
                    settlement_type=SettlementType.CASH,
                ),
                calendar=TradingCalendar(
                    first_notice_date=None,
                    last_trade_date=date(2026, 9, 18),
                    last_safe_trade_date=date(2026, 9, 14),
                ),
            ),
        }
    )

    assert json.loads(path.read_text(encoding="utf-8")) == [
        {
            "calendar": {
                "first_notice_date": None,
                "last_safe_trade_date": "2026-09-14",
                "last_trade_date": "2026-09-18",
            },
            "instrument_id": "ES-202609-CME",
            "spec": {
                "contract_month": "202609",
                "currency": "USD",
                "exchange": "CME",
                "multiplier": "50",
                "settlement_type": "cash",
                "symbol": "ES",
                "tick_size": "0.25",
            },
        },
        {
            "calendar": {
                "first_notice_date": "2026-11-30",
                "last_safe_trade_date": "2026-11-27",
                "last_trade_date": "2026-12-14",
            },
            "instrument_id": "ZC-202612-CBOT",
            "spec": {
                "contract_month": "202612",
                "currency": "USD",
                "exchange": "CBOT",
                "multiplier": "5000",
                "settlement_type": "physical",
                "symbol": "ZC",
                "tick_size": "0.25",
            },
        },
    ]
    assert store.load()["ZC-202612-CBOT"].delivery_sensitive is True


def test_json_instrument_store_rejects_missing_file(tmp_path):
    store = _store_class()(tmp_path / "instruments.json")

    with pytest.raises(ValueError, match="instrument catalog file does not exist"):
        store.load()


def test_json_instrument_store_rejects_duplicate_instruments(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(
        json.dumps(
            [
                {
                    "calendar": {
                        "first_notice_date": None,
                        "last_safe_trade_date": "2026-09-14",
                        "last_trade_date": "2026-09-18",
                    },
                    "instrument_id": "ES-202609-CME",
                    "spec": {
                        "contract_month": "202609",
                        "currency": "USD",
                        "exchange": "CME",
                        "multiplier": "50",
                        "settlement_type": "cash",
                        "symbol": "ES",
                        "tick_size": "0.25",
                    },
                },
                {
                    "calendar": {
                        "first_notice_date": None,
                        "last_safe_trade_date": "2026-09-15",
                        "last_trade_date": "2026-09-18",
                    },
                    "instrument_id": "ES-202609-CME",
                    "spec": {
                        "contract_month": "202609",
                        "currency": "USD",
                        "exchange": "CME",
                        "multiplier": "50",
                        "settlement_type": "cash",
                        "symbol": "ES",
                        "tick_size": "0.25",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )
    store = _store_class()(path)

    with pytest.raises(ValueError, match="duplicate instrument"):
        store.load()


def test_json_instrument_store_rejects_malformed_records(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text('[{"instrument_id":"ES-202609-CME"}]', encoding="utf-8")
    store = _store_class()(path)

    with pytest.raises(ValueError, match="invalid instrument record"):
        store.load()
