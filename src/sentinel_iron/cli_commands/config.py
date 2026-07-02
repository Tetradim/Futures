from __future__ import annotations

import os
import sys

from sentinel_iron.brokers.ibkr.config import load_ibkr_config
from sentinel_iron.brokers.ninjatrader.config import load_ninjatrader_config
from sentinel_iron.brokers.optimus.config import load_optimus_config
from sentinel_iron.brokers.tradestation.config import load_tradestation_config


def config_check(broker: str | None) -> int:
    selected_broker = (broker or os.environ.get("BROKER") or "ibkr").strip().lower()
    try:
        message = _load_config_message(selected_broker)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(message)
    return 0


def _load_config_message(broker: str) -> str:
    if broker == "ibkr":
        config = load_ibkr_config(os.environ)
        return (
            "IBKR config ok: "
            f"environment={config.environment.value} "
            f"host={config.host} "
            f"port={config.port} "
            f"client_id={config.client_id}"
        )
    if broker == "tradestation":
        config = load_tradestation_config(os.environ)
        return (
            "TradeStation config ok: "
            f"environment={config.environment.value} "
            f"base_url={config.base_url} "
            f"account_id={config.account_id}"
        )
    if broker == "ninjatrader":
        config = load_ninjatrader_config(os.environ)
        return (
            "NinjaTrader config ok: "
            f"environment={config.environment.value} "
            f"rest_url={config.rest_url} "
            f"websocket_url={config.websocket_url} "
            f"account_id={config.account_id}"
        )
    if broker == "optimus":
        config = load_optimus_config(os.environ)
        return (
            "Optimus config ok: "
            f"environment={config.environment.value} "
            f"route={config.route.value} "
            f"account_id={config.account_id} "
            f"api_url={config.api_url or 'not-set'}"
        )
    raise ValueError(f"unsupported broker: {broker}")
