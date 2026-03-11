# Tests

## What This Folder Is Trying To Accomplish

Validate core trading-system behavior with focused automated tests so refactors do not break signal logic, state contracts, or provider adapters.

## What Is Implemented

- `test_state.py`
  - Validates `MarketState` accessors/basic invariants.
- `test_events.py`
  - Validates event model fields.
- `test_rules.py`
  - Covers `PercentDropRule` and `MovingAverageCrossRule` behavior.
- `test_engine.py`
  - Checks signal aggregation through `SignalEngine`.
- `test_ibkr_fetcher.py`
  - High-value behavior tests for IBKR historical fetcher using a fake gateway
    (pagination, deduplication, overrides, depth sorting, pacing error mapping).
- `test_utility_functions.py`, `test_allocation.py`, `test_utility_allocation_strategy.py`
  - Validate shared utility math and production-facing utility allocation logic.

## What Still Needs To Be Implemented

- Strategy tests for `BuyDipStrategy` once decision logic exists.
- Risk-manager tests once limits are enforced.
- End-to-end integration tests for:
  - `TradingSystem.step()`
  - `backtest.py` workflow
  - `paper_trade.py` dry-run behavior
- Regression tests for `MultiSourceFetcher` and `CSVFetcher` after implementation.

## Suggested Next Step

Add first integration test that runs one synthetic bar stream through `TradingSystem` and asserts emitted events, portfolio changes, and fills end-to-end.
