from __future__ import annotations

import importlib
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from futures_bot.brokers.ibkr.adapter import IbkrClientError


ACCOUNT_SUMMARY_TAGS = "NetLiquidation,InitMarginReq,MaintMarginReq,BuyingPower"


@dataclass(frozen=True)
class IbapiModules:
    EClient: type
    EWrapper: type
    Contract: type
    Order: type


def load_ibapi_modules() -> IbapiModules:
    try:
        client_module = importlib.import_module("ibapi.client")
        wrapper_module = importlib.import_module("ibapi.wrapper")
        contract_module = importlib.import_module("ibapi.contract")
        order_module = importlib.import_module("ibapi.order")
    except ModuleNotFoundError as exc:
        raise IbkrClientError(
            "ibapi package is required for IBKR live connectivity",
            "IBAPI_MISSING",
        ) from exc

    return IbapiModules(
        EClient=client_module.EClient,
        EWrapper=wrapper_module.EWrapper,
        Contract=contract_module.Contract,
        Order=order_module.Order,
    )


class IbapiTwsClient:
    def __init__(
        self,
        app_factory: Callable[[], Any] | None = None,
        thread_factory: Callable[..., Any] = threading.Thread,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._app_factory = app_factory
        self._thread_factory = thread_factory
        self._timeout_seconds = timeout_seconds
        self._app: Any | None = None
        self._thread: Any | None = None

    def connect(self, host: str, port: int, client_id: int) -> None:
        app = self._app_factory() if self._app_factory is not None else create_ibapi_app(load_ibapi_modules())
        self._app = app
        try:
            app.connect(host, port, client_id)
            self._thread = self._thread_factory(target=app.run, daemon=True)
            self._thread.start()
            app.wait_until_connected(self._timeout_seconds)
        except IbkrClientError:
            raise
        except Exception as exc:
            raise IbkrClientError(str(exc), "IBAPI_CONNECT_FAILED") from exc

    def account_summary(self) -> tuple[Mapping[str, object], ...]:
        return self._require_app().request_account_summary(self._timeout_seconds)

    def positions(self) -> tuple[Mapping[str, object], ...]:
        return self._require_app().request_positions(self._timeout_seconds)

    def next_order_id(self) -> int:
        return self._require_app().next_order_id(self._timeout_seconds)

    def place_order(
        self,
        order_id: int,
        contract: Mapping[str, object],
        order: Mapping[str, object],
    ) -> None:
        self._require_app().place_order_payload(order_id, contract, order)

    def cancel_order(self, order_id: int) -> None:
        self._require_app().cancel_order_by_id(order_id)

    def historical_daily_bars(
        self,
        contract: Mapping[str, object],
        start_day: date,
        end_day: date,
    ) -> tuple[Mapping[str, object], ...]:
        return self._require_app().request_historical_daily_bars(
            contract,
            start_day,
            end_day,
            self._timeout_seconds,
        )

    def _require_app(self) -> Any:
        if self._app is None:
            raise IbkrClientError("IBKR TWS client is not connected", "IBAPI_NOT_CONNECTED")
        return self._app


def create_ibapi_app(modules: IbapiModules) -> Any:
    class IbapiApp(modules.EWrapper, modules.EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            modules.EClient.__init__(self, self)
            self._next_request_id = 1
            self._next_order_id: int | None = None
            self._next_order_id_event = threading.Event()
            self._account_requests: dict[int, tuple[list[Mapping[str, object]], threading.Event]] = {}
            self._historical_requests: dict[int, tuple[list[Mapping[str, object]], threading.Event]] = {}
            self._position_rows: list[Mapping[str, object]] = []
            self._position_event = threading.Event()
            self._request_errors: dict[int, IbkrClientError] = {}
            self._global_error: IbkrClientError | None = None

        def wait_until_connected(self, timeout_seconds: float) -> None:
            if not self._next_order_id_event.wait(timeout_seconds):
                self._raise_pending_error(-1)
                raise IbkrClientError("timed out waiting for IBKR nextValidId", "IBAPI_TIMEOUT")

        def request_account_summary(self, timeout_seconds: float) -> tuple[Mapping[str, object], ...]:
            req_id = self._allocate_request_id()
            rows: list[Mapping[str, object]] = []
            event = threading.Event()
            self._account_requests[req_id] = (rows, event)
            self.reqAccountSummary(req_id, "All", ACCOUNT_SUMMARY_TAGS)
            if not event.wait(timeout_seconds):
                self._raise_pending_error(req_id)
                raise IbkrClientError("timed out waiting for IBKR account summary", "IBAPI_TIMEOUT")
            self._raise_pending_error(req_id)
            self.cancelAccountSummary(req_id)
            return tuple(rows)

        def request_positions(self, timeout_seconds: float) -> tuple[Mapping[str, object], ...]:
            self._position_rows = []
            self._position_event = threading.Event()
            self.reqPositions()
            if not self._position_event.wait(timeout_seconds):
                self._raise_pending_error(-1)
                raise IbkrClientError("timed out waiting for IBKR positions", "IBAPI_TIMEOUT")
            self._raise_pending_error(-1)
            self.cancelPositions()
            return tuple(self._position_rows)

        def next_order_id(self, timeout_seconds: float) -> int:
            if not self._next_order_id_event.wait(timeout_seconds):
                self._raise_pending_error(-1)
                raise IbkrClientError("timed out waiting for IBKR nextValidId", "IBAPI_TIMEOUT")
            if self._next_order_id is None:
                raise IbkrClientError("IBKR nextValidId was not set", "IBAPI_NO_ORDER_ID")
            order_id = self._next_order_id
            self._next_order_id += 1
            return order_id

        def place_order_payload(
            self,
            order_id: int,
            contract: Mapping[str, object],
            order: Mapping[str, object],
        ) -> None:
            try:
                self.placeOrder(
                    order_id,
                    _object_from_mapping(modules.Contract, contract),
                    _object_from_mapping(modules.Order, order),
                )
            except Exception as exc:
                raise IbkrClientError(str(exc), "IBAPI_PLACE_ORDER_FAILED") from exc

        def cancel_order_by_id(self, order_id: int) -> None:
            try:
                try:
                    self.cancelOrder(order_id)
                except TypeError:
                    self.cancelOrder(order_id, "")
            except Exception as exc:
                raise IbkrClientError(str(exc), "IBAPI_CANCEL_FAILED") from exc

        def request_historical_daily_bars(
            self,
            contract: Mapping[str, object],
            start_day: date,
            end_day: date,
            timeout_seconds: float,
        ) -> tuple[Mapping[str, object], ...]:
            if start_day > end_day:
                raise IbkrClientError("start_day cannot be after end_day", "IBAPI_INVALID_DATE_RANGE")

            req_id = self._allocate_request_id()
            rows: list[Mapping[str, object]] = []
            event = threading.Event()
            self._historical_requests[req_id] = (rows, event)
            duration_days = (end_day - start_day).days + 1
            try:
                self.reqHistoricalData(
                    req_id,
                    _object_from_mapping(modules.Contract, contract),
                    f"{end_day.strftime('%Y%m%d')} 23:59:59 UTC",
                    f"{duration_days} D",
                    "1 day",
                    "TRADES",
                    0,
                    1,
                    False,
                    [],
                )
            except Exception as exc:
                raise IbkrClientError(str(exc), "IBAPI_HISTORICAL_DATA_FAILED") from exc
            if not event.wait(timeout_seconds):
                self._raise_pending_error(req_id)
                raise IbkrClientError("timed out waiting for IBKR historical data", "IBAPI_TIMEOUT")
            self._raise_pending_error(req_id)
            return tuple(rows)

        def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBKR callback name
            self._next_order_id = orderId
            self._next_order_id_event.set()

        def accountSummary(  # noqa: N802 - IBKR callback name
            self,
            reqId: int,
            account: str,
            tag: str,
            value: str,
            currency: str,
        ) -> None:
            request = self._account_requests.get(reqId)
            if request is None:
                return
            rows, _event = request
            rows.append(
                {
                    "account": account,
                    "tag": tag,
                    "value": value,
                    "currency": currency,
                }
            )

        def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802 - IBKR callback name
            request = self._account_requests.get(reqId)
            if request is not None:
                _rows, event = request
                event.set()

        def position(self, account: str, contract: object, position: object, avgCost: object) -> None:
            self._position_rows.append(
                {
                    "account": account,
                    "contract": _contract_mapping(contract),
                    "position": str(position),
                    "average_cost": str(avgCost),
                }
            )

        def positionEnd(self) -> None:  # noqa: N802 - IBKR callback name
            self._position_event.set()

        def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802 - IBKR callback name
            request = self._historical_requests.get(reqId)
            if request is None:
                return
            rows, _event = request
            rows.append(_historical_bar_mapping(bar))

        def historicalDataEnd(  # noqa: N802 - IBKR callback name
            self,
            reqId: int,
            start: str,
            end: str,
        ) -> None:
            request = self._historical_requests.get(reqId)
            if request is not None:
                _rows, event = request
                event.set()

        def error(  # noqa: A003, N802 - IBKR callback name
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            error = IbkrClientError(errorString, str(errorCode))
            if reqId >= 0:
                self._request_errors[reqId] = error
                request = self._account_requests.get(reqId)
                if request is not None:
                    _rows, event = request
                    event.set()
                historical_request = self._historical_requests.get(reqId)
                if historical_request is not None:
                    _rows, event = historical_request
                    event.set()
            else:
                self._global_error = error
                self._position_event.set()
                self._next_order_id_event.set()

        def _allocate_request_id(self) -> int:
            req_id = self._next_request_id
            self._next_request_id += 1
            return req_id

        def _raise_pending_error(self, req_id: int) -> None:
            error = self._request_errors.get(req_id)
            if error is not None:
                raise error
            if self._global_error is not None:
                raise self._global_error

    return IbapiApp()


def _object_from_mapping(object_type: type, values: Mapping[str, object]) -> object:
    item = object_type()
    for key, value in values.items():
        setattr(item, key, value)
    return item


def _contract_mapping(contract: object) -> Mapping[str, object]:
    keys = (
        "currency",
        "exchange",
        "lastTradeDateOrContractMonth",
        "localSymbol",
        "secType",
        "symbol",
    )
    return {
        key: value
        for key in keys
        if (value := getattr(contract, key, None)) not in (None, "")
    }


def _historical_bar_mapping(bar: object) -> Mapping[str, object]:
    keys = ("date", "open", "high", "low", "close", "volume")
    return {
        key: str(value)
        for key in keys
        if (value := getattr(bar, key, None)) is not None
    }
