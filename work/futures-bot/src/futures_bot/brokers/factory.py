from __future__ import annotations

from collections.abc import Callable
from typing import Mapping

from futures_bot.brokers.ibkr import IbkrClientPort
from futures_bot.brokers.routes import create_broker_route
from futures_bot.ports.broker import BrokerPort


def create_broker(
    name: str,
    env: Mapping[str, str],
    ibkr_client_factory: Callable[[], IbkrClientPort] | None = None,
) -> BrokerPort:
    return create_broker_route(
        name,
        env,
        ibkr_client_factory=ibkr_client_factory,
    ).execution
