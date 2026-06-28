from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from futures_bot.brokers.ibkr.config import load_ibkr_config
from futures_bot.brokers.ninjatrader.config import load_ninjatrader_config
from futures_bot.brokers.optimus.config import load_optimus_config
from futures_bot.brokers.tradestation.config import load_tradestation_config

FLATTEN_CONFIRMATION = "FLATTEN-LIVE-POSITIONS"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "config-check":
        return _config_check(args.broker)
    if args.command == "reconcile":
        return _reconcile()
    if args.command == "flatten":
        return _flatten(args.confirm)

    parser.print_help(sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="futures-bot")
    subparsers = parser.add_subparsers(dest="command")

    config_check = subparsers.add_parser("config-check", help="Validate broker configuration.")
    config_check.add_argument(
        "--broker",
        default=None,
        help=(
            "Broker to validate: ibkr, tradestation, ninjatrader, or optimus. "
            "Defaults to BROKER or ibkr."
        ),
    )
    subparsers.add_parser("reconcile", help="Reconcile internal and broker positions.")

    flatten = subparsers.add_parser("flatten", help="Flatten live broker positions.")
    flatten.add_argument("--confirm", default="", help=f"Must equal {FLATTEN_CONFIRMATION}.")

    return parser


def _config_check(broker: str | None) -> int:
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


def _reconcile() -> int:
    print("No live broker adapter is wired for reconciliation yet.", file=sys.stderr)
    return 1


def _flatten(confirm: str) -> int:
    if confirm != FLATTEN_CONFIRMATION:
        print(f"flatten requires --confirm {FLATTEN_CONFIRMATION}", file=sys.stderr)
        return 2
    print("No live broker adapter is wired for flatten yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
