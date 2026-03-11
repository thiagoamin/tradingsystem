# Allocation

## GOAL

Provide shared portfolio-allocation primitives that are reusable in both:

- research backtests
- live/paper trading execution paths

## IMPLEMENETED

- `utility_functions.py`
  - `UtilityFunction` contract.
  - `MeanVarianceUtility`, `LogUtility`, `ExponentialUtility`.
- `allocator.py`
  - `AssetEstimate` forecast container.
  - `UtilityAllocator` for score -> weights -> share targets conversion.
- `__init__.py`
  - Public exports for clean imports.

## TODO

- Multi-asset covariance-aware optimization (current allocator uses per-asset utility only).
- Turnover and transaction-cost penalties in weight generation.
- Shorting/market-neutral constraints where required.