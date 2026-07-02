from datetime import date, timedelta

from sentinel_iron.market.roll import ContractLiquidity, RollConfig, RollDecision, evaluate_roll


def _liquidity(
    instrument_id: str,
    volume: int,
    open_interest: int,
    last_safe_trade_date: date,
) -> ContractLiquidity:
    return ContractLiquidity(
        instrument_id=instrument_id,
        volume=volume,
        open_interest=open_interest,
        last_safe_trade_date=last_safe_trade_date,
    )


def test_rolls_when_current_contract_is_inside_roll_window():
    current = _liquidity("CL-202609-NYMEX", 1000, 5000, date(2026, 8, 28))
    next_contract = _liquidity("CL-202610-NYMEX", 700, 3000, date(2026, 9, 28))

    decision = evaluate_roll(
        today=date(2026, 8, 25),
        current=current,
        next_contract=next_contract,
        config=RollConfig(days_before_last_safe_trade=5, liquidity_ratio=1.2),
    )

    assert decision == RollDecision(
        should_roll=True,
        from_instrument_id="CL-202609-NYMEX",
        to_instrument_id="CL-202610-NYMEX",
        reason="inside_roll_window",
    )


def test_rolls_when_next_contract_volume_exceeds_ratio():
    current = _liquidity("ES-202609-CME", 1000, 9000, date(2026, 9, 18))
    next_contract = _liquidity("ES-202612-CME", 1300, 7000, date(2026, 12, 18))

    decision = evaluate_roll(
        today=date(2026, 8, 1),
        current=current,
        next_contract=next_contract,
        config=RollConfig(days_before_last_safe_trade=3, liquidity_ratio=1.2),
    )

    assert decision.should_roll is True
    assert decision.reason == "next_volume_dominates"


def test_rolls_when_next_contract_open_interest_exceeds_ratio():
    current = _liquidity("ZN-202609-CBOT", 1000, 5000, date(2026, 9, 18))
    next_contract = _liquidity("ZN-202612-CBOT", 900, 7000, date(2026, 12, 18))

    decision = evaluate_roll(
        today=date(2026, 8, 1),
        current=current,
        next_contract=next_contract,
        config=RollConfig(days_before_last_safe_trade=3, liquidity_ratio=1.2),
    )

    assert decision.should_roll is True
    assert decision.reason == "next_open_interest_dominates"


def test_holds_current_contract_when_no_roll_rule_triggers():
    current = _liquidity("ES-202609-CME", 2000, 9000, date(2026, 9, 18))
    next_contract = _liquidity("ES-202612-CME", 1800, 8000, date(2026, 12, 18))

    decision = evaluate_roll(
        today=date(2026, 8, 1),
        current=current,
        next_contract=next_contract,
        config=RollConfig(days_before_last_safe_trade=3, liquidity_ratio=1.2),
    )

    assert decision == RollDecision(
        should_roll=False,
        from_instrument_id="ES-202609-CME",
        to_instrument_id="ES-202609-CME",
        reason="hold_current",
    )


def test_roll_config_rejects_non_positive_liquidity_ratio():
    try:
        RollConfig(days_before_last_safe_trade=3, liquidity_ratio=0)
    except ValueError as exc:
        assert str(exc) == "liquidity_ratio must be greater than 1"
    else:
        raise AssertionError("expected invalid ratio to be rejected")


def test_contract_liquidity_rejects_negative_volume():
    try:
        _liquidity("ES-202609-CME", -1, 100, date.today() + timedelta(days=30))
    except ValueError as exc:
        assert str(exc) == "volume cannot be negative"
    else:
        raise AssertionError("expected negative volume to be rejected")
