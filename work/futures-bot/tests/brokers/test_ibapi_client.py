from __future__ import annotations

import importlib

import pytest


class FakeEWrapper:
    pass


class FakeContract:
    pass


class FakeOrder:
    pass


class FakeEClient:
    def __init__(self, wrapper: object) -> None:
        self.wrapper = wrapper
        self.calls: list[tuple[object, ...]] = []
        self.placed_orders: list[tuple[int, FakeContract, FakeOrder]] = []
        self.canceled_order_ids: list[int] = []

    def connect(self, host: str, port: int, client_id: int) -> None:
        self.calls.append(("connect", host, port, client_id))
        self.wrapper.nextValidId(9001)

    def run(self) -> None:
        self.calls.append(("run",))

    def reqAccountSummary(self, req_id: int, group: str, tags: str) -> None:
        self.calls.append(("reqAccountSummary", req_id, group, tags))
        self.wrapper.accountSummary(req_id, "DU12345", "NetLiquidation", "100000.50", "USD")
        self.wrapper.accountSummary(req_id, "DU12345", "InitMarginReq", "12000.25", "USD")
        self.wrapper.accountSummary(req_id, "DU12345", "MaintMarginReq", "9000.75", "USD")
        self.wrapper.accountSummary(req_id, "DU12345", "BuyingPower", "50000.00", "USD")
        self.wrapper.accountSummaryEnd(req_id)

    def cancelAccountSummary(self, req_id: int) -> None:
        self.calls.append(("cancelAccountSummary", req_id))

    def reqPositions(self) -> None:
        self.calls.append(("reqPositions",))
        contract = FakeContract()
        contract.localSymbol = "ESU6"
        contract.symbol = "ES"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.lastTradeDateOrContractMonth = "202609"
        contract.currency = "USD"
        self.wrapper.position("DU12345", contract, 2, 5000.25)
        self.wrapper.positionEnd()

    def cancelPositions(self) -> None:
        self.calls.append(("cancelPositions",))

    def placeOrder(self, order_id: int, contract: FakeContract, order: FakeOrder) -> None:
        self.placed_orders.append((order_id, contract, order))

    def cancelOrder(self, order_id: int) -> None:
        self.canceled_order_ids.append(order_id)


def _modules():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiModules

    return IbapiModules(
        EClient=FakeEClient,
        EWrapper=FakeEWrapper,
        Contract=FakeContract,
        Order=FakeOrder,
    )


class ImmediateThread:
    def __init__(self, target: object, daemon: bool) -> None:
        self.target = target
        self.daemon = daemon
        self.started = False

    def start(self) -> None:
        self.started = True
        self.target()


def test_ibapi_tws_client_connects_and_starts_message_loop():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiTwsClient, create_ibapi_app

    client = IbapiTwsClient(
        app_factory=lambda: create_ibapi_app(_modules()),
        thread_factory=ImmediateThread,
        timeout_seconds=0.01,
    )

    client.connect("127.0.0.1", 7497, 101)

    assert client._app.calls == [
        ("connect", "127.0.0.1", 7497, 101),
        ("run",),
    ]


def test_ibapi_tws_client_collects_account_summary_rows():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiTwsClient, create_ibapi_app

    client = IbapiTwsClient(
        app_factory=lambda: create_ibapi_app(_modules()),
        thread_factory=ImmediateThread,
        timeout_seconds=0.01,
    )
    client.connect("127.0.0.1", 7497, 101)

    rows = client.account_summary()

    assert rows == (
        {"account": "DU12345", "tag": "NetLiquidation", "value": "100000.50", "currency": "USD"},
        {"account": "DU12345", "tag": "InitMarginReq", "value": "12000.25", "currency": "USD"},
        {"account": "DU12345", "tag": "MaintMarginReq", "value": "9000.75", "currency": "USD"},
        {"account": "DU12345", "tag": "BuyingPower", "value": "50000.00", "currency": "USD"},
    )
    assert ("reqAccountSummary", 1, "All", "NetLiquidation,InitMarginReq,MaintMarginReq,BuyingPower") in client._app.calls
    assert ("cancelAccountSummary", 1) in client._app.calls


def test_ibapi_tws_client_collects_position_rows():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiTwsClient, create_ibapi_app

    client = IbapiTwsClient(
        app_factory=lambda: create_ibapi_app(_modules()),
        thread_factory=ImmediateThread,
        timeout_seconds=0.01,
    )
    client.connect("127.0.0.1", 7497, 101)

    positions = client.positions()

    assert positions == (
        {
            "account": "DU12345",
            "contract": {
                "currency": "USD",
                "exchange": "CME",
                "lastTradeDateOrContractMonth": "202609",
                "localSymbol": "ESU6",
                "secType": "FUT",
                "symbol": "ES",
            },
            "position": "2",
            "average_cost": "5000.25",
        },
    )
    assert ("reqPositions",) in client._app.calls
    assert ("cancelPositions",) in client._app.calls


def test_ibapi_tws_client_places_order_with_ibapi_objects():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiTwsClient, create_ibapi_app

    client = IbapiTwsClient(
        app_factory=lambda: create_ibapi_app(_modules()),
        thread_factory=ImmediateThread,
        timeout_seconds=0.01,
    )
    client.connect("127.0.0.1", 7497, 101)

    order_id = client.next_order_id()
    client.place_order(
        order_id=order_id,
        contract={
            "currency": "USD",
            "exchange": "CME",
            "lastTradeDateOrContractMonth": "202609",
            "secType": "FUT",
            "symbol": "ES",
        },
        order={
            "action": "BUY",
            "lmtPrice": "5000.25",
            "orderRef": "client-1",
            "orderType": "LMT",
            "tif": "DAY",
            "totalQuantity": 2,
        },
    )

    placed_order_id, contract, order = client._app.placed_orders[0]
    assert placed_order_id == 9001
    assert contract.symbol == "ES"
    assert contract.secType == "FUT"
    assert contract.exchange == "CME"
    assert contract.lastTradeDateOrContractMonth == "202609"
    assert contract.currency == "USD"
    assert order.action == "BUY"
    assert order.orderType == "LMT"
    assert order.totalQuantity == 2
    assert order.lmtPrice == "5000.25"
    assert order.tif == "DAY"
    assert order.orderRef == "client-1"


def test_ibapi_tws_client_cancels_order_id():
    from futures_bot.brokers.ibkr.ibapi_client import IbapiTwsClient, create_ibapi_app

    client = IbapiTwsClient(
        app_factory=lambda: create_ibapi_app(_modules()),
        thread_factory=ImmediateThread,
        timeout_seconds=0.01,
    )
    client.connect("127.0.0.1", 7497, 101)

    client.cancel_order(9001)

    assert client._app.canceled_order_ids == [9001]


def test_ibapi_tws_client_reports_missing_ibapi_dependency(monkeypatch):
    import futures_bot.brokers.ibkr.ibapi_client as ibapi_client
    from futures_bot.brokers.ibkr.adapter import IbkrClientError

    def missing_import(name: str):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", missing_import)

    with pytest.raises(IbkrClientError, match="ibapi package is required for IBKR live connectivity"):
        ibapi_client.load_ibapi_modules()
