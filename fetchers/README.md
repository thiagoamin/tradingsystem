# Fetchers Layer

## What This Folder Is Trying To Accomplish

Provide a unified market-data interface across providers so the rest of the system uses one canonical model/API regardless of source.

## What Is Implemented

- `models.py`
  - Canonical data classes (`OHLCVBar`, `L1Quote`, `TradePrint`, L2 models).
- `base.py`
  - Provider interface (`Fetcher`) + capability declarations + common errors.
- `providers/ibkr.py`
  - Extensive IBKR support for historical bars, L1 quotes, historical trades, L2 snapshots, and live order support hooks.
- `cache.py`
  - Wrapper structure for cached bar responses.
- `__init__.py`
  - Package exports.

## What Still Needs To Be Implemented

- `aggregator.py` (`MultiSourceFetcher`)
  - Capability merge.
  - Provider routing logic.
  - Fan-out/fan-in request execution.
- `cache.py`
  - Harden cache key behavior and persistence/TTL strategy.
- Better cross-provider normalization tests.

## Suggested Next Step

Finish `MultiSourceFetcher` so symbol routing and default-provider fallback work, then add integration tests against at least two provider implementations.
