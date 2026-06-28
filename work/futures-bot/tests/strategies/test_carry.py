from datetime import date
from decimal import Decimal

import pytest

from futures_bot.strategies.carry import CurveContract, CarrySignal, calculate_carry_signal


def test_carry_signal_is_positive_for_backwardation():
    signal = calculate_carry_signal(
        instrument_id="CL",
        front=CurveContract(
            instrument_id="CL-202609-NYMEX",
            expiration=date(2026, 9, 21),
            price=Decimal("82"),
        ),
        deferred=CurveContract(
            instrument_id="CL-202612-NYMEX",
            expiration=date(2026, 12, 21),
            price=Decimal("80"),
        ),
    )

    assert signal == CarrySignal(
        instrument_id="CL",
        annualized_carry=Decimal("0.09782900026802465826856070759"),
        score=Decimal("1"),
    )


def test_carry_signal_is_negative_for_contango():
    signal = calculate_carry_signal(
        instrument_id="CL",
        front=CurveContract(
            instrument_id="CL-202609-NYMEX",
            expiration=date(2026, 9, 21),
            price=Decimal("80"),
        ),
        deferred=CurveContract(
            instrument_id="CL-202612-NYMEX",
            expiration=date(2026, 12, 21),
            price=Decimal("82"),
        ),
    )

    assert signal.score == Decimal("-1")
    assert signal.annualized_carry == Decimal("-0.1002747252747252747252747253")


def test_carry_signal_is_neutral_for_flat_curve():
    signal = calculate_carry_signal(
        instrument_id="ES",
        front=CurveContract(
            instrument_id="ES-202609-CME",
            expiration=date(2026, 9, 18),
            price=Decimal("5000"),
        ),
        deferred=CurveContract(
            instrument_id="ES-202612-CME",
            expiration=date(2026, 12, 18),
            price=Decimal("5000"),
        ),
    )

    assert signal.score == Decimal("0")
    assert signal.annualized_carry == Decimal("0")


def test_carry_signal_uses_expiration_spacing_for_annualization():
    signal = calculate_carry_signal(
        instrument_id="GC",
        front=CurveContract(
            instrument_id="GC-202608-COMEX",
            expiration=date(2026, 8, 27),
            price=Decimal("2400"),
        ),
        deferred=CurveContract(
            instrument_id="GC-202609-COMEX",
            expiration=date(2026, 9, 26),
            price=Decimal("2390"),
        ),
    )

    assert signal.annualized_carry == Decimal("0.05069444444444444444444444446")


def test_carry_signal_rejects_deferred_expiration_before_front():
    with pytest.raises(ValueError, match="deferred expiration must be after front expiration"):
        calculate_carry_signal(
            instrument_id="CL",
            front=CurveContract(
                instrument_id="CL-202612-NYMEX",
                expiration=date(2026, 12, 21),
                price=Decimal("80"),
            ),
            deferred=CurveContract(
                instrument_id="CL-202609-NYMEX",
                expiration=date(2026, 9, 21),
                price=Decimal("82"),
            ),
        )


def test_curve_contract_rejects_non_positive_price():
    with pytest.raises(ValueError, match="price must be positive"):
        CurveContract(
            instrument_id="CL-202609-NYMEX",
            expiration=date(2026, 9, 21),
            price=Decimal("0"),
        )
