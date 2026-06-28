from futures_bot.cli import main


def _set_valid_ibkr_env(monkeypatch):
    monkeypatch.setenv("BROKER_ENV", "paper")
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "7497")
    monkeypatch.setenv("IBKR_CLIENT_ID", "101")


def _set_valid_tradestation_env(monkeypatch):
    monkeypatch.setenv("BROKER_ENV", "paper")
    monkeypatch.setenv("TRADESTATION_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("TRADESTATION_ACCOUNT_ID", "SIM12345")


def _set_valid_ninjatrader_env(monkeypatch):
    monkeypatch.setenv("BROKER_ENV", "paper")
    monkeypatch.setenv("NINJATRADER_REST_URL", "https://api.ninjatrader.example/v1")
    monkeypatch.setenv("NINJATRADER_WS_URL", "wss://stream.ninjatrader.example/v1")
    monkeypatch.setenv("NINJATRADER_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("NINJATRADER_ACCOUNT_ID", "SIM12345")


def _set_valid_optimus_env(monkeypatch):
    monkeypatch.setenv("BROKER_ENV", "paper")
    monkeypatch.setenv("OPTIMUS_ROUTE", "rithmic")
    monkeypatch.setenv("OPTIMUS_USERNAME", "secret-user")
    monkeypatch.setenv("OPTIMUS_PASSWORD", "secret-password")
    monkeypatch.setenv("OPTIMUS_ACCOUNT_ID", "SIM12345")


def test_config_check_exits_zero_for_valid_ibkr_config(monkeypatch, capsys):
    _set_valid_ibkr_env(monkeypatch)

    exit_code = main(["config-check"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "IBKR config ok: environment=paper host=127.0.0.1 port=7497 client_id=101" in captured.out


def test_config_check_accepts_explicit_ibkr_broker(monkeypatch, capsys):
    _set_valid_ibkr_env(monkeypatch)

    exit_code = main(["config-check", "--broker", "ibkr"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "IBKR config ok" in captured.out


def test_config_check_exits_zero_for_valid_tradestation_config(monkeypatch, capsys):
    _set_valid_tradestation_env(monkeypatch)

    exit_code = main(["config-check", "--broker", "tradestation"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        "TradeStation config ok: "
        "environment=paper "
        "base_url=https://sim-api.tradestation.com/v3 "
        "account_id=SIM12345"
    ) in captured.out
    assert "secret-token" not in captured.out


def test_config_check_exits_zero_for_valid_ninjatrader_config(monkeypatch, capsys):
    _set_valid_ninjatrader_env(monkeypatch)

    exit_code = main(["config-check", "--broker", "ninjatrader"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        "NinjaTrader config ok: "
        "environment=paper "
        "rest_url=https://api.ninjatrader.example/v1 "
        "websocket_url=wss://stream.ninjatrader.example/v1 "
        "account_id=SIM12345"
    ) in captured.out
    assert "secret-token" not in captured.out


def test_config_check_exits_zero_for_valid_optimus_config(monkeypatch, capsys):
    _set_valid_optimus_env(monkeypatch)

    exit_code = main(["config-check", "--broker", "optimus"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        "Optimus config ok: "
        "environment=paper "
        "route=rithmic "
        "account_id=SIM12345 "
        "api_url=not-set"
    ) in captured.out
    assert "secret-user" not in captured.out
    assert "secret-password" not in captured.out


def test_config_check_uses_broker_environment_variable(monkeypatch, capsys):
    _set_valid_tradestation_env(monkeypatch)
    monkeypatch.setenv("BROKER", "tradestation")

    exit_code = main(["config-check"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TradeStation config ok" in captured.out


def test_config_check_rejects_unknown_broker(capsys):
    exit_code = main(["config-check", "--broker", "unknown"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "unsupported broker: unknown" in captured.err


def test_config_check_exits_nonzero_for_invalid_config(monkeypatch, capsys):
    _set_valid_ibkr_env(monkeypatch)
    monkeypatch.delenv("IBKR_HOST")

    exit_code = main(["config-check"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "IBKR_HOST is required" in captured.err


def test_reconcile_command_reports_no_broker_adapter_wired_yet(capsys):
    exit_code = main(["reconcile"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No live broker adapter is wired for reconciliation yet." in captured.err


def test_flatten_command_refuses_without_explicit_confirmation_text(capsys):
    exit_code = main(["flatten"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "flatten requires --confirm FLATTEN-LIVE-POSITIONS" in captured.err
