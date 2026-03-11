# Data Layer

## Goal

Provide the data plumbing between raw market feeds and the trading engine by:

1. Pulling bars/quotes from a fetcher.
2. Computing stateful indicators/features from bars.
3. Storing and serving latest feature values.

## Implemented:

- `feed.py`
  - `HistoricalFeed` and `LiveFeed` wrappers over the generic fetcher interface.
- `feature_store.py`
  - In-memory key-value store for latest `(symbol, feature_name) -> value`.
- `__init__.py`
  - Exposes clean imports for the data package.

## TODO:

- `feature_engine.py`
  - Real indicator computation is still missing.
  - `on_bar()` currently records history but returns `{}`.
  - Needs at minimum:
    - Daily returns.
    - Moving averages (for rule/strategy compatibility).
    - Volatility features.
    - Optional warm-up behavior and NaN handling.