from decimal import Decimal

import pytest

from futures_bot.strategies.composite import (
    CompositeSignal,
    WeightedSignal,
    combine_weighted_signals,
)


def test_combines_weighted_signals_into_weighted_average():
    signal = combine_weighted_signals(
        instrument_id="CL",
        signals=(
            WeightedSignal(name="trend", score=Decimal("1"), weight=Decimal("0.70")),
            WeightedSignal(name="carry", score=Decimal("-1"), weight=Decimal("0.30")),
        ),
    )

    assert signal == CompositeSignal(
        instrument_id="CL",
        score=Decimal("0.40"),
        components={"trend": Decimal("1"), "carry": Decimal("-1")},
    )


def test_clips_composite_signal_to_one():
    signal = combine_weighted_signals(
        instrument_id="CL",
        signals=(
            WeightedSignal(name="trend", score=Decimal("2"), weight=Decimal("1")),
            WeightedSignal(name="carry", score=Decimal("1"), weight=Decimal("1")),
        ),
    )

    assert signal.score == Decimal("1")


def test_clips_composite_signal_to_negative_one():
    signal = combine_weighted_signals(
        instrument_id="CL",
        signals=(
            WeightedSignal(name="trend", score=Decimal("-2"), weight=Decimal("1")),
            WeightedSignal(name="carry", score=Decimal("-1"), weight=Decimal("1")),
        ),
    )

    assert signal.score == Decimal("-1")


def test_rejects_empty_signal_set():
    with pytest.raises(ValueError, match="signals are required"):
        combine_weighted_signals(instrument_id="CL", signals=())


def test_rejects_non_positive_weight():
    with pytest.raises(ValueError, match="weight must be positive"):
        WeightedSignal(name="trend", score=Decimal("1"), weight=Decimal("0"))


def test_rejects_duplicate_signal_names():
    with pytest.raises(ValueError, match="signal names must be unique"):
        combine_weighted_signals(
            instrument_id="CL",
            signals=(
                WeightedSignal(name="trend", score=Decimal("1"), weight=Decimal("1")),
                WeightedSignal(name="trend", score=Decimal("-1"), weight=Decimal("1")),
            ),
        )
