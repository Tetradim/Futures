import pytest

from futures_bot.brokers.tradestation.config import (
    BrokerEnvironment,
    TradeStationConfig,
    load_tradestation_config,
)


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "BROKER_ENV": "paper",
        "TRADESTATION_ACCESS_TOKEN": "token-123",
        "TRADESTATION_ACCOUNT_ID": "SIM12345",
    }
    env.update(overrides)
    return env


def test_valid_paper_config_uses_sim_api_default_base_url():
    config = load_tradestation_config(_env())

    assert config == TradeStationConfig(
        environment=BrokerEnvironment.PAPER,
        base_url="https://sim-api.tradestation.com/v3",
        access_token="token-123",
        account_id="SIM12345",
    )


def test_valid_live_config_uses_live_api_default_base_url():
    config = load_tradestation_config(
        _env(BROKER_ENV="live", TRADESTATION_ACCOUNT_ID="LIVE12345")
    )

    assert config.environment == BrokerEnvironment.LIVE
    assert config.base_url == "https://api.tradestation.com/v3"
    assert config.account_id == "LIVE12345"


def test_base_url_override_is_supported():
    config = load_tradestation_config(
        _env(TRADESTATION_BASE_URL="https://proxy.example.test/tradestation")
    )

    assert config.base_url == "https://proxy.example.test/tradestation"


def test_unsupported_environment_is_rejected():
    with pytest.raises(ValueError, match="BROKER_ENV must be one of"):
        load_tradestation_config(_env(BROKER_ENV="sandbox"))


def test_missing_access_token_is_rejected():
    env = _env()
    env.pop("TRADESTATION_ACCESS_TOKEN")

    with pytest.raises(ValueError, match="TRADESTATION_ACCESS_TOKEN is required"):
        load_tradestation_config(env)


def test_missing_account_id_is_rejected():
    env = _env()
    env.pop("TRADESTATION_ACCOUNT_ID")

    with pytest.raises(ValueError, match="TRADESTATION_ACCOUNT_ID is required"):
        load_tradestation_config(env)


def test_invalid_base_url_is_rejected():
    with pytest.raises(ValueError, match="TRADESTATION_BASE_URL must be an http or https URL"):
        load_tradestation_config(_env(TRADESTATION_BASE_URL="not-a-url"))
