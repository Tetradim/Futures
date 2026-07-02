# Sentinel Iron Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first live-capable Sentinel Iron core with tested domain models, pre-trade risk controls, broker ports, IBKR configuration skeleton, and operational CLI commands.

**Architecture:** Use clean architecture. Domain and application layers remain pure Python and have no broker SDK dependencies. Broker-specific code lives behind ports so IBKR, TradeStation, NinjaTrader, and Optimus routes can be added without changing strategy or risk code.

**Tech Stack:** Python 3.11+, stdlib dataclasses/enums/decimal/argparse, pytest for tests, optional broker SDKs isolated in future infrastructure adapters.

---

## File Structure

- `pyproject.toml`: package metadata, pytest config, console script.
- `README.md`: setup, safety model, commands, limitations.
- `src/sentinel_iron/__init__.py`: package version.
- `src/sentinel_iron/domain/enums.py`: shared enums for orders, settlement, and risk reason codes.
- `src/sentinel_iron/domain/instruments.py`: futures instrument specs, tick calculations, delivery cutoff logic.
- `src/sentinel_iron/domain/orders.py`: order intents and broker-ready order model.
- `src/sentinel_iron/domain/portfolio.py`: account, position, and market snapshot models.
- `src/sentinel_iron/risk/engine.py`: deterministic pre-trade risk engine.
- `src/sentinel_iron/ports/broker.py`: broker adapter interface.
- `src/sentinel_iron/ports/audit.py`: audit log interface and in-memory implementation for tests.
- `src/sentinel_iron/application/reconciliation.py`: reconciliation use case.
- `src/sentinel_iron/brokers/ibkr/config.py`: IBKR environment config loader and validator.
- `src/sentinel_iron/cli.py`: operational CLI commands.
- `tests/`: pytest coverage for each behavior before implementation.

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/sentinel_iron/__init__.py`
- Create: `tests/test_package.py`
- Create: `.gitignore`

- [ ] **Step 1: Write the failing package import test**

```python
from sentinel_iron import __version__


def test_package_exposes_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_package.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'sentinel_iron'`.

- [ ] **Step 3: Add minimal package configuration and version**

Create `pyproject.toml` with package metadata, pytest path, and CLI script. Create `src/sentinel_iron/__init__.py` containing `__version__ = "0.1.0"`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_package.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add .gitignore pyproject.toml src/sentinel_iron/__init__.py tests/test_package.py
git commit -m "Add Sentinel Iron Python package skeleton"
```

## Task 2: Futures Instrument Domain

**Files:**
- Create: `src/sentinel_iron/domain/enums.py`
- Create: `src/sentinel_iron/domain/instruments.py`
- Create: `tests/domain/test_instruments.py`

- [ ] **Step 1: Write failing tests for tick math and cutoff logic**

Tests must cover:

- tick value calculation from multiplier and tick size
- rounding prices to the nearest valid tick
- blocking contracts after the last safe trade date
- marking physically settled instruments as delivery-sensitive

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/domain/test_instruments.py -v`

Expected: FAIL because `sentinel_iron.domain.instruments` does not exist.

- [ ] **Step 3: Implement enums and instrument models**

Implement `SettlementType`, `ContractSpec`, `TradingCalendar`, and `FuturesInstrument`. Use `Decimal` for prices, multipliers, and tick sizes.

- [ ] **Step 4: Run the instrument tests**

Run: `python -m pytest tests/domain/test_instruments.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/domain/enums.py src/sentinel_iron/domain/instruments.py tests/domain/test_instruments.py
git commit -m "Add futures instrument domain model"
```

## Task 3: Orders And Portfolio Models

**Files:**
- Create: `src/sentinel_iron/domain/orders.py`
- Create: `src/sentinel_iron/domain/portfolio.py`
- Create: `tests/domain/test_orders_portfolio.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- order intents require positive quantity
- limit orders require a limit price
- market orders do not require a limit price
- positions compute the signed quantity after an order side
- account margin usage is `initial_margin / equity`

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/domain/test_orders_portfolio.py -v`

Expected: FAIL because order and portfolio modules do not exist.

- [ ] **Step 3: Implement order and portfolio models**

Implement `OrderSide`, `OrderType`, `OrderIntent`, `BrokerOrder`, `Position`, `AccountSnapshot`, and `MarketSnapshot`.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/domain/test_orders_portfolio.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/domain/orders.py src/sentinel_iron/domain/portfolio.py tests/domain/test_orders_portfolio.py
git commit -m "Add order and portfolio domain models"
```

## Task 4: Pre-Trade Risk Engine

**Files:**
- Create: `src/sentinel_iron/risk/engine.py`
- Create: `tests/risk/test_engine.py`

- [ ] **Step 1: Write failing risk tests**

Tests must cover rejection for:

- active kill switch
- unreconciled positions
- stale account snapshot
- stale market data
- max order quantity breach
- max resulting position breach
- max margin usage breach
- expired or delivery-sensitive contract past cutoff
- duplicate client order ID
- limit price outside collar

Tests must also cover an approved order returning an approved `RiskDecision`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/risk/test_engine.py -v`

Expected: FAIL because `sentinel_iron.risk.engine` does not exist.

- [ ] **Step 3: Implement the minimal risk engine**

Implement `RiskLimits`, `RiskContext`, `RiskDecision`, and `RiskEngine.evaluate(intent, context)`. Return stable risk reason codes from `RiskReason`.

- [ ] **Step 4: Run the risk tests**

Run: `python -m pytest tests/risk/test_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/risk/engine.py tests/risk/test_engine.py
git commit -m "Add pre-trade risk engine"
```

## Task 5: Ports, Audit, And Reconciliation

**Files:**
- Create: `src/sentinel_iron/ports/broker.py`
- Create: `src/sentinel_iron/ports/audit.py`
- Create: `src/sentinel_iron/application/reconciliation.py`
- Create: `tests/application/test_reconciliation.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- broker position and internal position match approves trading
- missing internal position for a broker position rejects trading
- quantity mismatch rejects trading
- in-memory audit log records immutable event dictionaries

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/application/test_reconciliation.py -v`

Expected: FAIL because application and ports modules do not exist.

- [ ] **Step 3: Implement ports and reconciliation use case**

Use `typing.Protocol` for ports. Keep broker SDK dependencies out of the port definitions.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/application/test_reconciliation.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/ports/broker.py src/sentinel_iron/ports/audit.py src/sentinel_iron/application/reconciliation.py tests/application/test_reconciliation.py
git commit -m "Add broker ports and reconciliation use case"
```

## Task 6: IBKR Configuration Skeleton

**Files:**
- Create: `src/sentinel_iron/brokers/ibkr/config.py`
- Create: `tests/brokers/test_ibkr_config.py`

- [ ] **Step 1: Write failing config tests**

Tests must cover:

- valid paper config loads from a mapping
- valid live config loads from a mapping
- unsupported broker environment is rejected
- missing host is rejected
- invalid port is rejected
- invalid client ID is rejected

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/brokers/test_ibkr_config.py -v`

Expected: FAIL because `sentinel_iron.brokers.ibkr.config` does not exist.

- [ ] **Step 3: Implement config loader**

Implement `BrokerEnvironment`, `IbkrConfig`, and `load_ibkr_config(env: Mapping[str, str])`.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/brokers/test_ibkr_config.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/brokers/ibkr/config.py tests/brokers/test_ibkr_config.py
git commit -m "Add IBKR broker configuration skeleton"
```

## Task 7: Operational CLI

**Files:**
- Create: `src/sentinel_iron/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Tests must cover:

- `config-check` exits zero for valid IBKR config
- `config-check` exits non-zero for invalid config
- `reconcile` command exists and reports that no broker adapter is wired yet
- `flatten` command exists and refuses to run without explicit confirmation text

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`

Expected: FAIL because `sentinel_iron.cli` does not exist.

- [ ] **Step 3: Implement argparse CLI**

Implement `main(argv: list[str] | None = None) -> int` and register the console script `sentinel-iron`.

- [ ] **Step 4: Run the CLI tests**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/sentinel_iron/cli.py tests/test_cli.py pyproject.toml
git commit -m "Add operational CLI safety commands"
```

## Task 8: Documentation And Full Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Document:

- safety-first scope
- install command
- required environment variables
- `config-check`, `reconcile`, and `flatten` commands
- current limitation that no live order submission is enabled yet
- next broker adapter targets

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests -v`

Expected: PASS.

- [ ] **Step 3: Inspect git status**

Run: `git status --short`

Expected: only README changes before commit.

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md
git commit -m "Document Sentinel Iron core setup"
```

## Self-Review

- The plan maps every first-slice acceptance criterion from the design spec to at least one task.
- The plan keeps broker SDKs out of the domain and application layers.
- The first broker implementation is deliberately a configuration skeleton, not live order submission.
- Every behavior task starts with failing tests and verifies the failure before implementation.
- No strategy code is included before risk, reconciliation, and operator commands exist.
