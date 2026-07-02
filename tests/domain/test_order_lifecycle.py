import pytest

from sentinel_iron.domain.order_lifecycle import OrderLifecycle, OrderLifecycleStatus


def test_order_lifecycle_accepts_working_from_pending_submit():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1")

    updated = lifecycle.mark_working()

    assert updated.status == OrderLifecycleStatus.WORKING
    assert updated.filled_quantity == 0


def test_order_lifecycle_accumulates_partial_fills():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    updated = lifecycle.record_fill(fill_quantity=2, order_quantity=5)

    assert updated.status == OrderLifecycleStatus.PARTIALLY_FILLED
    assert updated.filled_quantity == 2


def test_order_lifecycle_marks_filled_when_cumulative_fill_reaches_order_quantity():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    partially_filled = lifecycle.record_fill(fill_quantity=2, order_quantity=5)
    filled = partially_filled.record_fill(fill_quantity=3, order_quantity=5)

    assert filled.status == OrderLifecycleStatus.FILLED
    assert filled.filled_quantity == 5


def test_order_lifecycle_allows_pending_cancel_from_working():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    updated = lifecycle.mark_pending_cancel()

    assert updated.status == OrderLifecycleStatus.PENDING_CANCEL


def test_order_lifecycle_allows_canceled_from_pending_cancel():
    lifecycle = (
        OrderLifecycle.pending_submit(client_order_id="order-1")
        .mark_working()
        .mark_pending_cancel()
    )

    updated = lifecycle.mark_canceled()

    assert updated.status == OrderLifecycleStatus.CANCELED


def test_order_lifecycle_allows_rejected_from_pending_submit():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1")

    updated = lifecycle.mark_rejected(reason="broker rejected order")

    assert updated.status == OrderLifecycleStatus.REJECTED
    assert updated.reject_reason == "broker rejected order"


def test_order_lifecycle_rejects_cancel_after_fill():
    lifecycle = (
        OrderLifecycle.pending_submit(client_order_id="order-1")
        .mark_working()
        .record_fill(fill_quantity=5, order_quantity=5)
    )

    with pytest.raises(ValueError, match="cannot transition from filled to pending_cancel"):
        lifecycle.mark_pending_cancel()


def test_order_lifecycle_rejects_fill_quantity_above_order_quantity():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    with pytest.raises(ValueError, match="filled quantity cannot exceed order quantity"):
        lifecycle.record_fill(fill_quantity=6, order_quantity=5)


def test_order_lifecycle_rejects_non_positive_fill_quantity():
    lifecycle = OrderLifecycle.pending_submit(client_order_id="order-1").mark_working()

    with pytest.raises(ValueError, match="fill_quantity must be positive"):
        lifecycle.record_fill(fill_quantity=0, order_quantity=5)
