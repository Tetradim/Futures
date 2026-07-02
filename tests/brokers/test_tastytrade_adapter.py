from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

import pytest

from sentinel_iron.application.rebalance_risk_context import MarginEstimate
from sentinel_iron.brokers.tastytrade.config import BrokerEnvironment, TastytradeConfig
from sentinel_iron.domain.enums import OrderSide, OrderType
from sentinel_iron.domain.orders import BrokerOrder
from sentinel_iron.domain.portfolio import Position
from sentinel_iron.ports.broker import (
    BrokerCancellationError,
    BrokerConnectionError,
    BrokerSubmissionError,
)


NOW = datetime(2026, 6, 29, 2, 18, tzinfo=timezone.utc)


class RecordingTransport:
    def __init__(self, responses: tuple[object | None, ...]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None = None,
    ) -> object | None:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": dict(body) if body is not None else None,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected tastytrade request")
        return self.responses.pop(0)


class FailingTransport(RecordingTransport):
    def __init__(self, reason: str, status_code: int = 400, broker_error_code: str = "bad_request") -> None:
        super().__init__(())
        self.reason = reason
        self.status_code = status_code
        self.broker_error_code = broker_error_code

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None = None,
    ) -> object | None:
        from sentinel_iron.brokers.tastytrade.adapter import TastytradeHttpError

        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": dict(body) if body is not None else None,
            }
        )
        raise TastytradeHttpError(self.reason, self.status_code, self.broker_error_code)


def _config() -> TastytradeConfig:
    return TastytradeConfig(
        environment=BrokerEnvironment.PAPER,
        base_url="https://api.cert.tastytrade.com",
        session_token="session-token-123",
        customer_id="98765",
        account_number="5WX12345",
    )


def _adapter(transport: RecordingTransport):
    from sentinel_iron.brokers.tastytrade.adapter import TastytradeBroker

    return TastytradeBroker(config=_config(), transport=transport, clock=lambda: NOW)


def test_tastytrade_connect_validates_open_futures_account_with_session_auth():
    transport = RecordingTransport(
        (
            {
                "data": {
                    "items": [
                        {
                            "account": {
                                "account-number": "5WX12345",
                                "is-closed": False,
                                "is-futures-approved": True,
                            },
                            "authority-level": "owner",
                        }
                    ]
                }
            },
        )
    )
    broker = _adapter(transport)

    broker.connect()

    assert transport.requests == [
        {
            "method": "GET",
            "url": "https://api.cert.tastytrade.com/customers/98765/accounts",
            "headers": {"Authorization": "session-token-123", "Content-Type": "application/json"},
            "body": None,
        }
    ]


def test_tastytrade_connect_rejects_non_futures_account():
    transport = RecordingTransport(
        (
            {
                "data": {
                    "items": [
                        {
                            "account": {
                                "account-number": "5WX12345",
                                "is-closed": False,
                                "is-futures-approved": False,
                            }
                        }
                    ]
                }
            },
        )
    )
    broker = _adapter(transport)

    with pytest.raises(BrokerConnectionError, match="configured tastytrade futures account was not returned"):
        broker.connect()


def test_tastytrade_get_account_maps_balance_payload():
    transport = RecordingTransport(
        (
            {
                "data": {
                    "account-number": "5WX12345",
                    "net-liquidating-value": "100000.50",
                    "futures-margin-requirement": "12000.25",
                    "maintenance-requirement": "9000.75",
                    "available-trading-funds": "50000.00",
                    "updated-at": "2026-06-29T02:18:00Z",
                }
            },
        )
    )
    broker = _adapter(transport)

    account = broker.get_account()

    assert account.account_id == "5WX12345"
    assert account.equity == Decimal("100000.50")
    assert account.initial_margin == Decimal("12000.25")
    assert account.maintenance_margin == Decimal("9000.75")
    assert account.buying_power == Decimal("50000.00")
    assert account.timestamp == NOW
    assert transport.requests[0]["url"] == "https://api.cert.tastytrade.com/accounts/5WX12345/balances"


def test_tastytrade_get_positions_filters_futures_and_maps_short_quantity():
    transport = RecordingTransport(
        (
            {
                "data": {
                    "items": [
                        {
                            "account-number": "5WX12345",
                            "instrument-type": "Future",
                            "symbol": "/ESU6",
                            "quantity": "2",
                            "quantity-direction": "Long",
                            "average-open-price": "5000.25",
                        },
                        {
                            "account-number": "5WX12345",
                            "instrument-type": "Future",
                            "symbol": "/NQU6",
                            "quantity": "1",
                            "quantity-direction": "Short",
                            "average-open-price": "18000.50",
                        },
                        {
                            "account-number": "5WX12345",
                            "instrument-type": "Equity",
                            "symbol": "SPY",
                            "quantity": "10",
                            "quantity-direction": "Long",
                        },
                    ]
                }
            },
        )
    )
    broker = _adapter(transport)

    positions = broker.get_positions()

    assert positions == (
        Position("/ESU6", 2, Decimal("5000.25")),
        Position("/NQU6", -1, Decimal("18000.50")),
    )
    assert transport.requests[0]["url"] == "https://api.cert.tastytrade.com/accounts/5WX12345/positions"


def test_tastytrade_submit_order_posts_future_limit_order_and_returns_order_id():
    transport = RecordingTransport(({"data": {"order": {"id": 987654321}}},))
    broker = _adapter(transport)

    broker_order_id = broker.submit_order(
        BrokerOrder(
            instrument_id="/ESU6",
            side=OrderSide.BUY,
            quantity=2,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("5000.25"),
            client_order_id="client-1",
        )
    )

    assert broker_order_id == "987654321"
    assert transport.requests == [
        {
            "method": "POST",
            "url": "https://api.cert.tastytrade.com/accounts/5WX12345/orders",
            "headers": {"Authorization": "session-token-123", "Content-Type": "application/json"},
            "body": {
                "advanced-instructions": {"strict-position-effect-validation": False},
                "automated-source": True,
                "external-identifier": "client-1",
                "legs": [
                    {
                        "action": "Buy",
                        "instrument-type": "Future",
                        "quantity": 2,
                        "symbol": "/ESU6",
                    }
                ],
                "order-type": "Limit",
                "price": "5000.25",
                "price-effect": "Debit",
                "time-in-force": "Day",
                "value-effect": "Debit",
            },
        }
    ]


def test_tastytrade_submit_order_maps_http_errors_to_submission_error():
    transport = FailingTransport("order rejected: market closed", 400, "market_closed")
    broker = _adapter(transport)

    with pytest.raises(BrokerSubmissionError) as exc_info:
        broker.submit_order(
            BrokerOrder(
                instrument_id="/ESU6",
                side=OrderSide.SELL,
                quantity=1,
                order_type=OrderType.MARKET,
                client_order_id="client-2",
            )
        )

    assert exc_info.value.reason == "order rejected: market closed"
    assert exc_info.value.broker_error_code == "market_closed"


def test_tastytrade_estimates_order_margin_with_dry_run_endpoint():
    transport = RecordingTransport(
        (
            {
                "data": {
                    "initial-margin-requirement": "12000.25",
                    "maintenance-margin-requirement": "9000.75",
                }
            },
        )
    )
    broker = _adapter(transport)

    estimate = broker.estimate_order_margin(
        BrokerOrder(
            instrument_id="/ESU6",
            side=OrderSide.SELL,
            quantity=1,
            order_type=OrderType.MARKET,
            client_order_id="client-3",
        )
    )

    assert estimate == MarginEstimate(
        initial_margin=Decimal("12000.25"),
        maintenance_margin=Decimal("9000.75"),
    )
    assert transport.requests[0]["method"] == "POST"
    assert transport.requests[0]["url"] == "https://api.cert.tastytrade.com/margin/accounts/5WX12345/dry-run"
    assert transport.requests[0]["body"]["legs"][0]["action"] == "Sell"


def test_tastytrade_cancel_order_posts_cancel_request():
    transport = RecordingTransport(({"data": {"id": 987654321}},))
    broker = _adapter(transport)

    broker.cancel_order("987654321")

    assert transport.requests == [
        {
            "method": "DELETE",
            "url": "https://api.cert.tastytrade.com/accounts/5WX12345/orders/987654321",
            "headers": {"Authorization": "session-token-123", "Content-Type": "application/json"},
            "body": None,
        }
    ]


def test_tastytrade_cancel_order_maps_http_errors_to_cancellation_error():
    transport = FailingTransport("too late to cancel", 400, "too_late_to_cancel")
    broker = _adapter(transport)

    with pytest.raises(BrokerCancellationError) as exc_info:
        broker.cancel_order("987654321")

    assert exc_info.value.reason == "too late to cancel"
    assert exc_info.value.broker_error_code == "too_late_to_cancel"
