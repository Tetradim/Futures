from __future__ import annotations

from futures_bot.brokers.tastytrade.config import (
    BrokerEnvironment,
    load_tastytrade_config,
)


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "BROKER_ENV": "paper",
        "TASTYTRADE_SESSION_TOKEN": "session-token-123",
        "TASTYTRADE_CUSTOMER_ID": "98765",
        "TASTYTRADE_ACCOUNT_NUMBER": "5WX12345",
    }
    env.update(overrides)
    return env


def test_load_tastytrade_config_uses_certification_base_url_for_paper():
    config = load_tastytrade_config(_env())

    assert config.environment == BrokerEnvironment.PAPER
    assert config.base_url == "https://api.cert.tastytrade.com"
    assert config.session_token == "session-token-123"
    assert config.customer_id == "98765"
    assert config.account_number == "5WX12345"


def test_load_tastytrade_config_uses_production_base_url_for_live():
    config = load_tastytrade_config(_env(BROKER_ENV="live"))

    assert config.environment == BrokerEnvironment.LIVE
    assert config.base_url == "https://api.tastytrade.com"


def test_load_tastytrade_config_accepts_explicit_base_url():
    config = load_tastytrade_config(
        _env(TASTYTRADE_BASE_URL="https://tastytrade-proxy.example.test/api")
    )

    assert config.base_url == "https://tastytrade-proxy.example.test/api"


def test_load_tastytrade_config_requires_session_token():
    try:
        load_tastytrade_config(_env(TASTYTRADE_SESSION_TOKEN=" "))
    except ValueError as exc:
        assert str(exc) == "TASTYTRADE_SESSION_TOKEN is required"
    else:
        raise AssertionError("expected missing token to be rejected")


def test_load_tastytrade_config_rejects_invalid_environment():
    try:
        load_tastytrade_config(_env(BROKER_ENV="sandbox"))
    except ValueError as exc:
        assert str(exc) == "BROKER_ENV must be one of: paper, live"
    else:
        raise AssertionError("expected invalid environment to be rejected")
