# Data

Pluggable data sources for research panels.

Every source implements the same ABC and returns a ``DailyEodPanels``. An
experiment depends on the abstract ``DataSource``, not on the underlying
fetcher; swapping cached for live, or merging multiple sources, is a config
change rather than an experiment edit.

## Implementation map

- [base.py](base.py)
  - `UniverseSpec` (stocks + factor ETFs + splits)
  - `PanelRequest` (universe + date window)
  - `DataSource` (ABC)
- [cached.py](cached.py)
  - `CachedPanelSource` -- reads `eod_raw_close_panel.csv` (+ optional volume)
    from a cache directory and re-runs `build_daily_eod_panels`.
- [thetadata.py](thetadata.py)
  - `ThetaPanelSource` -- fetches via the existing `ThetaDataEodIngestor`,
    optionally writes the cache projection so a later `CachedPanelSource`
    can reuse it.
- [layered.py](layered.py)
  - `LayeredPanelSource` -- ordered fallback chain. First source whose
    `get_panels` does not raise ``FileNotFoundError`` wins.

## Typical usage

The Avellaneda--Lee experiments hit a layered cache-first source:

```python
from research.tools.data import (
    CachedPanelSource,
    LayeredPanelSource,
    PanelRequest,
    ThetaPanelSource,
    UniverseSpec,
)

universe = UniverseSpec(
    stocks=tuple(TECH_STOCKS),
    factor_etfs=("XLK", "SPY", "QQQ"),
    split_events=tuple(RAW_CLOSE_SPLIT_EVENTS),
)
source = LayeredPanelSource([
    CachedPanelSource(cache_root),
    ThetaPanelSource(cache_root=cache_root),
])
panels = source.get_panels(PanelRequest(universe, start_date, end_date))
```

To run the same experiment from cache only (e.g. offline development), drop
the ``ThetaPanelSource`` from the layer list. To force a fresh fetch and
re-materialize the cache, pass only ``ThetaPanelSource(cache_root=...)``.

## Where to extend

- New file feed (e.g. parquet): subclass `DataSource`, implement
  `get_panels`, and accept whatever paths/credentials its store needs.
- New provider (e.g. Polygon, Norgate): mirror the pattern of
  `ThetaPanelSource` -- fetch records, then hand them to
  `build_daily_eod_panels` so downstream pipeline code stays identical.
- Synthetic / fixture sources for tests: construct a panel directly and
  return it from `get_panels`.

## Cache projection convention

When ``ThetaPanelSource(cache_root=...)`` writes the cache, it materialises
exactly two CSVs:

| File | Contents |
|---|---|
| `eod_raw_close_panel.csv` | Wide raw close panel indexed by `date`, columns are symbols, no splits applied. |
| `eod_raw_volume_panel.csv` | Wide raw share volume, same shape. Optional. |

This is the same on-disk layout the existing experiment ingestion scripts
have always written, so a fresh `ThetaPanelSource` cache and an existing
experiment cache are interchangeable.
