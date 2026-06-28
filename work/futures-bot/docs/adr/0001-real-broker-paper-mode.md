# ADR 0001: Treat Broker Paper Mode As Real Broker Connectivity

## Status

Accepted

## Context

The bot targets live-capable futures trading across Interactive Brokers, TradeStation, NinjaTrader, and Optimus Futures. Each broker can expose a paper or simulation environment, but those environments still depend on broker-specific credentials, account state, permissions, market data entitlements, order validation, margin behavior, and route semantics.

Using fake demo adapters in production-facing modules would create a second behavior path that can pass tests while bypassing the operational constraints that matter before live trading.

## Decision

Paper mode is treated as a real broker environment. Broker paper routes must use the same adapter family, route assembly, fail-closed error handling, audit logging, and capability checks as live routes.

The project will not add fake demo broker modes to production modules. Tests may use fakes at module seams, but those fakes must live in tests or explicit in-memory ports and must not be selectable as production broker routes.

## Consequences

- Broker route construction must expose explicit capabilities so unsupported margin or historical-data features fail closed.
- CLI and application workflows must wire through broker routes instead of ad hoc method probing.
- Paper environment bugs are production bugs because the same adapter path is expected to graduate to live credentials.
- Strategy modules receive normalized, verified inputs. They do not call broker adapters directly.
