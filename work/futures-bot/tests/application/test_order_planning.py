from decimal import Decimal

from futures_bot.application.order_planning import OrderPlanningConfig, plan_order_to_target
from futures_bot.domain.enums import OrderSide, OrderType
from futures_bot.domain.portfolio import Position
from futures_bot.portfolio.position_sizing import PositionTarget


def _position(quantity: int) -> Position:
    return Position(
        instrument_id="ES-202609-CME",
        quantity=quantity,
        average_price=Decimal("5000"),
    )


def test_plan_order_to_target_creates_buy_intent_for_positive_delta():
    intent = plan_order_to_target(
        target=PositionTarget(instrument_id="ES-202609-CME", quantity=5),
        current_position=_position(2),
        config=OrderPlanningConfig(client_order_prefix="rebalance", order_type=OrderType.MARKET),
    )

    assert intent is not None
    assert intent.side == OrderSide.BUY
    assert intent.quantity == 3
    assert intent.client_order_id == "rebalance-ES-202609-CME-buy-3"


def test_plan_order_to_target_creates_sell_intent_for_negative_delta():
    intent = plan_order_to_target(
        target=PositionTarget(instrument_id="ES-202609-CME", quantity=-2),
        current_position=_position(1),
        config=OrderPlanningConfig(client_order_prefix="rebalance", order_type=OrderType.MARKET),
    )

    assert intent is not None
    assert intent.side == OrderSide.SELL
    assert intent.quantity == 3
    assert intent.client_order_id == "rebalance-ES-202609-CME-sell-3"


def test_plan_order_to_target_returns_none_when_already_at_target():
    intent = plan_order_to_target(
        target=PositionTarget(instrument_id="ES-202609-CME", quantity=2),
        current_position=_position(2),
        config=OrderPlanningConfig(client_order_prefix="rebalance", order_type=OrderType.MARKET),
    )

    assert intent is None


def test_plan_order_to_target_propagates_limit_price():
    intent = plan_order_to_target(
        target=PositionTarget(instrument_id="ES-202609-CME", quantity=3),
        current_position=_position(1),
        config=OrderPlanningConfig(
            client_order_prefix="rebalance",
            order_type=OrderType.LIMIT,
            limit_price=Decimal("5001.25"),
        ),
    )

    assert intent is not None
    assert intent.order_type == OrderType.LIMIT
    assert intent.limit_price == Decimal("5001.25")


def test_order_planning_rejects_instrument_mismatch():
    try:
        plan_order_to_target(
            target=PositionTarget(instrument_id="NQ-202609-CME", quantity=3),
            current_position=_position(1),
            config=OrderPlanningConfig(client_order_prefix="rebalance", order_type=OrderType.MARKET),
        )
    except ValueError as exc:
        assert str(exc) == "target and current_position instruments must match"
    else:
        raise AssertionError("expected instrument mismatch to be rejected")
