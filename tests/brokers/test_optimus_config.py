import pytest

from sentinel_iron.brokers.optimus.config import (
    BrokerEnvironment,
    OptimusConfig,
    OptimusRoute,
    load_optimus_config,
)


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "BROKER_ENV": "paper",
        "OPTIMUS_ROUTE": "rithmic",
        "OPTIMUS_USERNAME": "user-123",
        "OPTIMUS_PASSWORD": "secret-password",
        "OPTIMUS_ACCOUNT_ID": "SIM12345",
    }
    env.update(overrides)
    return env


def test_valid_paper_config_requires_selected_execution_route():
    config = load_optimus_config(_env())

    assert config == OptimusConfig(
        environment=BrokerEnvironment.PAPER,
        route=OptimusRoute.RITHMIC,
        username="user-123",
        password="secret-password",
        account_id="SIM12345",
        api_url=None,
        app_name="sentinel-iron",
    )


def test_valid_live_config_accepts_gateway_url_and_app_name():
    config = load_optimus_config(
        _env(
            BROKER_ENV="live",
            OPTIMUS_ROUTE="cqg",
            OPTIMUS_ACCOUNT_ID="LIVE12345",
            OPTIMUS_API_URL="https://gateway.example.test/optimus",
            OPTIMUS_APP_NAME="production-worker-1",
        )
    )

    assert config.environment == BrokerEnvironment.LIVE
    assert config.route == OptimusRoute.CQG
    assert config.account_id == "LIVE12345"
    assert config.api_url == "https://gateway.example.test/optimus"
    assert config.app_name == "production-worker-1"


@pytest.mark.parametrize(
    ("raw_route", "expected"),
    [
        ("firetip", OptimusRoute.FIRETIP),
        ("cts", OptimusRoute.CTS),
        ("gain", OptimusRoute.GAIN),
        ("stonex", OptimusRoute.GAIN),
        ("tt", OptimusRoute.TRADING_TECHNOLOGIES),
        ("tradingtechnologies", OptimusRoute.TRADING_TECHNOLOGIES),
        ("trading_technologies", OptimusRoute.TRADING_TECHNOLOGIES),
        ("trading technologies", OptimusRoute.TRADING_TECHNOLOGIES),
        ("oak", OptimusRoute.OAK),
        ("qst", OptimusRoute.QUICK_SCREEN_TRADING),
        ("quick_screen_trading", OptimusRoute.QUICK_SCREEN_TRADING),
        ("quick screen trading", OptimusRoute.QUICK_SCREEN_TRADING),
    ],
)
def test_execution_route_aliases_are_accepted(raw_route, expected):
    config = load_optimus_config(_env(OPTIMUS_ROUTE=raw_route))

    assert config.route == expected


def test_unsupported_environment_is_rejected():
    with pytest.raises(ValueError, match="BROKER_ENV must be one of"):
        load_optimus_config(_env(BROKER_ENV="sandbox"))


def test_missing_route_is_rejected():
    env = _env()
    env.pop("OPTIMUS_ROUTE")

    with pytest.raises(ValueError, match="OPTIMUS_ROUTE is required"):
        load_optimus_config(env)


def test_unsupported_route_is_rejected():
    with pytest.raises(ValueError, match="OPTIMUS_ROUTE must be one of"):
        load_optimus_config(_env(OPTIMUS_ROUTE="unsupported"))


def test_missing_username_is_rejected():
    env = _env()
    env.pop("OPTIMUS_USERNAME")

    with pytest.raises(ValueError, match="OPTIMUS_USERNAME is required"):
        load_optimus_config(env)


def test_missing_password_is_rejected():
    env = _env()
    env.pop("OPTIMUS_PASSWORD")

    with pytest.raises(ValueError, match="OPTIMUS_PASSWORD is required"):
        load_optimus_config(env)


def test_invalid_gateway_url_is_rejected():
    with pytest.raises(ValueError, match="OPTIMUS_API_URL must be an http or https URL"):
        load_optimus_config(_env(OPTIMUS_API_URL="not-a-url"))
