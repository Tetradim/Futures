from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sentinel_iron.application.margin_estimates import MarginEstimateUnavailable
from sentinel_iron.application.rebalance_risk_context import MarginEstimate
from sentinel_iron.brokers.tastytrade.config import TastytradeConfig
from sentinel_iron.domain.enums import OrderSide, OrderType
from sentinel_iron.domain.orders import BrokerOrder
from sentinel_iron.domain.portfolio import AccountSnapshot, Position
from sentinel_iron.ports.broker import (
    BrokerCancellationError,
    BrokerConnectionError,
    BrokerSubmissionError,
)
from sentinel_iron.ports.market_data import HistoricalBar, MarketDataError


class TastytradeHttpError(RuntimeError):
    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
        broker_error_code: str | None = None,
    ) -> None:
        if not reason:
            raise ValueError("reason is required")
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code
        self.broker_error_code = broker_error_code


class TastytradeTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None = None,
    ) -> object | None:
        """Send one tastytrade HTTP request."""


class UrllibTastytradeTransport:
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object] | None = None,
    ) -> object | None:
        request_body = None
        if body is not None:
            request_body = json.dumps(body, separators=(",", ":")).encode("utf-8")

        request = Request(
            url=url,
            data=request_body,
            headers=dict(headers),
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            reason, broker_error_code = _extract_error(response_body)
            raise TastytradeHttpError(reason, exc.code, broker_error_code) from exc
        except URLError as exc:
            raise TastytradeHttpError(str(exc.reason), None, "NETWORK_ERROR") from exc

        if not response_body.strip():
            return None
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise TastytradeHttpError("tastytrade response was not valid JSON") from exc


@dataclass(frozen=True)
class TastytradeBroker:
    config: TastytradeConfig
    transport: TastytradeTransport | None = None
    clock: Callable[[], datetime] | None = None

    def __post_init__(self) -> None:
        if self.transport is None:
            object.__setattr__(self, "transport", UrllibTastytradeTransport())
        if self.clock is None:
            object.__setattr__(self, "clock", lambda: datetime.now(timezone.utc))

    def connect(self) -> None:
        try:
            accounts = _records(
                self._request("GET", f"/customers/{quote(self.config.customer_id, safe='')}/accounts")
            )
        except TastytradeHttpError as exc:
            raise BrokerConnectionError(exc.reason, exc.broker_error_code) from exc
        except ValueError as exc:
            raise BrokerConnectionError(str(exc)) from exc

        if not any(self._is_configured_open_futures_account(account) for account in accounts):
            raise BrokerConnectionError("configured tastytrade futures account was not returned")

    def get_account(self) -> AccountSnapshot:
        try:
            balance = _record(
                self._request(
                    "GET",
                    f"/accounts/{quote(self.config.account_number, safe='')}/balances",
                )
            )
            account_number = _required_text(balance, "account-number")
            if account_number != self.config.account_number:
                raise ValueError("balance account number did not match configured account")
            return AccountSnapshot(
                account_id=account_number,
                equity=_required_decimal(balance, "net-liquidating-value", "margin-equity"),
                initial_margin=_decimal(
                    balance,
                    "futures-margin-requirement",
                    "futures-overnight-margin-requirement",
                    default=Decimal("0"),
                ),
                maintenance_margin=_decimal(
                    balance,
                    "maintenance-requirement",
                    "futures-margin-requirement",
                    default=Decimal("0"),
                ),
                buying_power=_required_decimal(
                    balance,
                    "available-trading-funds",
                    "derivative-buying-power",
                    "maintenance-excess",
                ),
                timestamp=_timestamp(balance, self.clock),
            )
        except TastytradeHttpError as exc:
            raise BrokerConnectionError(exc.reason, exc.broker_error_code) from exc
        except ValueError as exc:
            raise BrokerConnectionError(str(exc)) from exc

    def get_positions(self) -> tuple[Position, ...]:
        try:
            positions = _records(
                self._request(
                    "GET",
                    f"/accounts/{quote(self.config.account_number, safe='')}/positions",
                )
            )
            return tuple(
                _position(position)
                for position in positions
                if _optional_text(position, "account-number") == self.config.account_number
                and _optional_text(position, "instrument-type") == "Future"
            )
        except TastytradeHttpError as exc:
            raise BrokerConnectionError(exc.reason, exc.broker_error_code) from exc
        except ValueError as exc:
            raise BrokerConnectionError(str(exc)) from exc

    def submit_order(self, order: BrokerOrder) -> str:
        try:
            payload = self._request(
                "POST",
                f"/accounts/{quote(self.config.account_number, safe='')}/orders",
                self._order_payload(order),
            )
            broker_order_id = _order_id(payload)
            if broker_order_id is None:
                raise ValueError("tastytrade order response did not include an order ID")
            return broker_order_id
        except TastytradeHttpError as exc:
            raise BrokerSubmissionError(exc.reason, exc.broker_error_code) from exc
        except ValueError as exc:
            raise BrokerSubmissionError(str(exc)) from exc

    def estimate_order_margin(self, order: BrokerOrder) -> MarginEstimate:
        try:
            payload = _record(
                self._request(
                    "POST",
                    f"/margin/accounts/{quote(self.config.account_number, safe='')}/dry-run",
                    self._order_payload(order),
                )
            )
            return MarginEstimate(
                initial_margin=_required_decimal(
                    payload,
                    "initial-margin-requirement",
                    "initial-requirement",
                    "margin-requirement",
                ),
                maintenance_margin=_required_decimal(
                    payload,
                    "maintenance-margin-requirement",
                    "maintenance-requirement",
                    "margin-requirement",
                ),
            )
        except TastytradeHttpError as exc:
            raise MarginEstimateUnavailable(exc.reason, exc.broker_error_code) from exc
        except ValueError as exc:
            raise MarginEstimateUnavailable(str(exc)) from exc

    def get_daily_bars(
        self,
        instrument_id: str,
        start_day: date,
        end_day: date,
    ) -> tuple[HistoricalBar, ...]:
        raise MarketDataError(
            "tastytrade adapter does not expose verified historical daily bars"
        )

    def cancel_order(self, broker_order_id: str) -> None:
        if not broker_order_id:
            raise ValueError("broker_order_id is required")
        try:
            self._request(
                "DELETE",
                (
                    f"/accounts/{quote(self.config.account_number, safe='')}"
                    f"/orders/{quote(broker_order_id, safe='')}"
                ),
            )
        except TastytradeHttpError as exc:
            raise BrokerCancellationError(exc.reason, exc.broker_error_code) from exc

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> object | None:
        assert self.transport is not None
        return self.transport.request(
            method=method,
            url=f"{self.config.base_url}{path}",
            headers={
                "Authorization": self.config.session_token,
                "Content-Type": "application/json",
            },
            body=body,
        )

    def _is_configured_open_futures_account(self, value: Mapping[str, object]) -> bool:
        account = value.get("account") if isinstance(value.get("account"), Mapping) else value
        if not isinstance(account, Mapping):
            raise ValueError("tastytrade account response was invalid")
        return (
            _optional_text(account, "account-number") == self.config.account_number
            and not bool(account.get("is-closed", False))
            and bool(account.get("is-futures-approved", False))
        )

    def _order_payload(self, order: BrokerOrder) -> Mapping[str, object]:
        payload: dict[str, object] = {
            "advanced-instructions": {"strict-position-effect-validation": False},
            "automated-source": True,
            "external-identifier": order.client_order_id,
            "legs": [
                {
                    "action": _action(order.side),
                    "instrument-type": "Future",
                    "quantity": order.quantity,
                    "symbol": order.instrument_id,
                }
            ],
            "order-type": _order_type(order.order_type),
            "price-effect": _price_effect(order.side),
            "time-in-force": "Day",
            "value-effect": _price_effect(order.side),
        }
        if order.order_type == OrderType.LIMIT:
            if order.limit_price is None:
                raise ValueError("limit price is required for tastytrade limit orders")
            payload["price"] = str(order.limit_price)
        return payload


def _extract_error(response_body: str) -> tuple[str, str | None]:
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return response_body.strip() or "tastytrade HTTP request failed", None
    if not isinstance(parsed, Mapping):
        return "tastytrade HTTP request failed", None

    error = parsed.get("error")
    if isinstance(error, Mapping):
        reason = (
            _optional_text(error, "message")
            or _optional_text(error, "reason")
            or "tastytrade HTTP request failed"
        )
        broker_error_code = _optional_text(error, "code")
        return reason, broker_error_code

    reason = (
        _optional_text(parsed, "message")
        or _optional_text(parsed, "error")
        or _optional_text(parsed, "reason")
        or "tastytrade HTTP request failed"
    )
    broker_error_code = _optional_text(parsed, "code", "error-code")
    return reason, broker_error_code


def _record(value: object | None) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        data = value.get("data")
        if isinstance(data, Mapping):
            return data
        return value
    raise ValueError("tastytrade response was invalid")


def _records(value: object | None) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        records = value
    elif isinstance(value, Mapping):
        data = value.get("data")
        if isinstance(data, Mapping) and isinstance(data.get("items"), list):
            records = data["items"]
        elif isinstance(data, list):
            records = data
        elif isinstance(value.get("items"), list):
            records = value["items"]
        else:
            records = [data if isinstance(data, Mapping) else value]
    else:
        raise ValueError("tastytrade response was invalid")

    parsed_records: list[Mapping[str, object]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("tastytrade response record was invalid")
        parsed_records.append(record)
    return tuple(parsed_records)


def _position(value: Mapping[str, object]) -> Position:
    quantity = int(_required_decimal(value, "quantity"))
    if _optional_text(value, "quantity-direction") == "Short":
        quantity = -quantity
    return Position(
        instrument_id=_required_text(value, "symbol"),
        quantity=quantity,
        average_price=_decimal(value, "average-open-price", "average-price", default=Decimal("0")),
    )


def _order_id(value: object | None) -> str | None:
    if not isinstance(value, Mapping):
        return None
    data = value.get("data")
    if isinstance(data, Mapping):
        order = data.get("order")
        if isinstance(order, Mapping):
            return _optional_text(order, "id", "order-id")
        return _optional_text(data, "id", "order-id")
    return _optional_text(value, "id", "order-id")


def _action(side: OrderSide) -> str:
    if side == OrderSide.BUY:
        return "Buy"
    if side == OrderSide.SELL:
        return "Sell"
    raise ValueError(f"unsupported order side: {side}")


def _price_effect(side: OrderSide) -> str:
    if side == OrderSide.BUY:
        return "Debit"
    if side == OrderSide.SELL:
        return "Credit"
    raise ValueError(f"unsupported order side: {side}")


def _order_type(order_type: OrderType) -> str:
    if order_type == OrderType.MARKET:
        return "Market"
    if order_type == OrderType.LIMIT:
        return "Limit"
    raise ValueError(f"unsupported order type: {order_type}")


def _required_text(value: Mapping[str, object], *names: str) -> str:
    text = _optional_text(value, *names)
    if text is None:
        label = " or ".join(names)
        raise ValueError(f"{label} is required")
    return text


def _optional_text(value: Mapping[str, object], *names: str) -> str | None:
    for name in names:
        raw_value = value.get(name)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            if not raw_value:
                continue
            return raw_value
        return str(raw_value)
    return None


def _required_decimal(value: Mapping[str, object], *names: str) -> Decimal:
    decimal = _optional_decimal(value, *names)
    if decimal is None:
        label = " or ".join(names)
        raise ValueError(f"{label} is required")
    return decimal


def _decimal(value: Mapping[str, object], *names: str, default: Decimal) -> Decimal:
    decimal = _optional_decimal(value, *names)
    return default if decimal is None else decimal


def _optional_decimal(value: Mapping[str, object], *names: str) -> Decimal | None:
    text = _optional_text(value, *names)
    if text is None:
        return None
    try:
        return Decimal(text)
    except Exception as exc:
        label = " or ".join(names)
        raise ValueError(f"{label} must be numeric") from exc


def _timestamp(
    value: Mapping[str, object],
    clock: Callable[[], datetime] | None,
) -> datetime:
    text = _optional_text(value, "updated-at", "created-at", "timestamp")
    if text is None:
        assert clock is not None
        return clock()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
