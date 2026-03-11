# Strategies

## What This Folder Is Trying To Accomplish

Hold concrete strategy implementations that convert signal events into executable position intents (`Action`s).

## What Is Implemented

- `basic.py` defines `BuyDipStrategy`.
- `utility_allocation.py` defines `UtilityAllocationStrategy` for production
  portfolio targeting using shared utility-based allocation.
- Package export in `__init__.py`.

## What Still Needs To Be Implemented

- `BuyDipStrategy.decide()` currently returns `[]` for every state.
- Needed behavior:
  - Parse signal events (e.g. `pct_drop`) and map to target quantities.
  - Generate `SetTargetPosition` actions for entries.
  - Add exit logic (profit target and/or signal invalidation).
  - Respect current holdings and avoid duplicate/redundant actions.
- Utility strategy enhancements still needed:
  - richer signal schema standardization (`expected_return`, `volatility`)
  - optional turnover/cost-aware rebalancing rules

## Suggested Next Step

Implement deterministic unit-tested decision logic for `pct_drop` entries and profit-target exits so the main system can place orders during backtests/paper runs.
