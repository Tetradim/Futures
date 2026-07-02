import pytest

from sentinel_iron.brokers.ninjatrader.config import (
    BrokerEnvironment,
    NinjaTraderConfig,
    load_ninjatrader_config,
)


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "BROKER_ENV": "paper",
        "NINJATRADER_REST_URL": "https://api.ninjatrader.example/v1",
        "NINJATRADER_WS_URL": "wss://stream.ninjatrader.example/v1",
        "NINJATRADER_ACCESS_TOKEN": "token-123",
        "NINJATRADER_ACCOUNT_ID": "SIM12345",
    }
    env.update(overrides)
    return env


def test_valid_paper_config_loads_from_mapping():
    config = load_ninjatrader_config(_env())

    assert config == NinjaTraderConfig(
        environment=BrokerEnvironment.PAPER,
        rest_url="https://api.ninjatrader.example/v1",
        websocket_url="wss://stream.ninjatrader.example/v1",
        access_token="token-123",
        account_id="SIM12345",
    )


def test_valid_live_config_loads_from_mapping():
    config = load_ninjatrader_config(
        _env(BROKER_ENV="live", NINJATRADER_ACCOUNT_ID="LIVE12345")
    )

    assert config.environment == BrokerEnvironment.LIVE
    assert config.account_id == "LIVE12345"


def test_unsupported_environment_is_rejected():
    with pytest.raises(ValueError, match="BROKER_ENV must be one of"):
        load_ninjatrader_config(_env(BROKER_ENV="sandbox"))


def test_missing_rest_url_is_rejected():
    env = _env()
    env.pop("NINJATRADER_REST_URL")

    with pytest.raises(ValueError, match="NINJATRADER_REST_URL is required"):
        load_ninjatrader_config(env)


def test_invalid_rest_url_is_rejected():
    with pytest.raises(ValueError, match="NINJATRADER_REST_URL must be an http or https URL"):
        load_ninjatrader_config(_env(NINJATRADER_REST_URL="ftp://example.test"))


def test_invalid_websocket_url_is_rejected():
    with pytest.raises(ValueError, match="NINJATRADER_WS_URL must be a ws or wss URL"):
        load_ninjatrader_config(_env(NINJATRADER_WS_URL="https://example.test/stream"))


def test_missing_access_token_is_rejected():
    env = _env()
    env.pop("NINJATRADER_ACCESS_TOKEN")

    with pytest.raises(ValueError, match="NINJATRADER_ACCESS_TOKEN is required"):
        load_ninjatrader_config(env)


def test_missing_account_id_is_rejected():
    env = _env()
    env.pop("NINJATRADER_ACCOUNT_ID")

    with pytest.raises(ValueError, match="NINJATRADER_ACCOUNT_ID is required"):
        load_ninjatrader_config(env)
