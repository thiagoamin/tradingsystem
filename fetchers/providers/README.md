# Providers

## GOAL

Host concrete provider adapters that implement the generic `Fetcher` interface for specific data/execution vendors.

## Implemented:

- `ibkr.py`
  - Full IBKR historical-market-data adapter with contract normalization, pagination, pacing safeguards, and model conversion.
  - Live adapter support used by paper/live execution path.
- `__init__.py`
  - Provider exports and aliases.

## TODO:

- `csv.py`
  - CSV data parsing and normalization are not implemented.
  - Should support bar loading for offline backtests.
- Optional future work:
  - Additional providers (e.g., Polygon/Alpaca) behind the same `Fetcher` contract.
  - Consistent provider-level config management and credential handling.