from __future__ import annotations

"""Ingest and split-adjust ThetaData EOD records for the sector-ETF experiment."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.fetchers.thetadata import ThetaDataEodIngestor
from research.fetchers.thetadata.theta_storage import ThetaDataStorage
from research.tools.processing import DailyEodPanels, build_daily_eod_panels

from .config import (
    CONFIGURED_SPLITS,
    END_DATE,
    FACTOR_ETFS,
    START_DATE,
    STOCKS,
    SYMBOLS,
    configured_split_frame,
    universe_frame,
)

OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "sector_etf"
    / "theta_eod_ingestion"
)
SPLIT_LIKE_ABS_LOG_RETURN = 0.45


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> DailyEodPanels:
    """Fetch raw ThetaData EOD records and write split-adjusted sector panels."""
    ingestor = ThetaDataEodIngestor(dataframe_type="pandas")
    result = ingestor.ingest(SYMBOLS, start_date=start_date, end_date=end_date, reuse_cache=True)
    return _build_and_write(result.records, result.paths, output_root)


def load_cached_panels(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> DailyEodPanels:
    """Load cached raw experiment closes and reapply configured split adjustments."""
    raw_path = output_root / "eod_raw_close_panel.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw EOD panel is absent; run ingestion first: {raw_path}")
    raw_closes = pd.read_csv(raw_path, index_col="date", parse_dates=["date"])
    raw_closes = raw_closes.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]
    raw_volumes = _read_optional_cached_panel(
        output_root / "eod_raw_volume_panel.csv", start_date=start_date, end_date=end_date
    )
    records = _records_from_cached_panels(raw_closes, raw_volumes)
    storage = ThetaDataStorage()
    return _build_and_write(
        records, {symbol: storage.raw_eod_path(symbol) for symbol in SYMBOLS}, output_root
    )


def load_or_fetch_panels(refresh_data: bool = False) -> DailyEodPanels:
    """Use cached EOD records when available, or fetch the raw universe once.

    Implemented via the layered DataSource in ``research.tools.data``: cache
    first, ThetaData fallback. The function name and signature are preserved
    so existing callers (e.g. ``multi_sector_hybrid_nested_tuning``) keep
    working unchanged. Set ``refresh_data=True`` to skip the cache and always
    re-fetch.
    """
    from research.tools.data import (
        CachedPanelSource,
        LayeredPanelSource,
        PanelRequest,
        ThetaPanelSource,
        UniverseSpec,
    )

    universe = UniverseSpec(
        stocks=tuple(STOCKS),
        factor_etfs=tuple(FACTOR_ETFS),
        split_events=tuple(CONFIGURED_SPLITS),
    )
    request = PanelRequest(universe=universe, start_date=START_DATE, end_date=END_DATE)
    layers = (
        [ThetaPanelSource(cache_root=OUTPUT_ROOT)]
        if refresh_data
        else [CachedPanelSource(OUTPUT_ROOT), ThetaPanelSource(cache_root=OUTPUT_ROOT)]
    )
    return LayeredPanelSource(layers).get_panels(request)


def _build_and_write(
    records: pd.DataFrame, paths: dict[str, Path], output_root: Path
) -> DailyEodPanels:
    panels = build_daily_eod_panels(
        records, STOCKS, FACTOR_ETFS, split_events=CONFIGURED_SPLITS
    )
    output_root.mkdir(parents=True, exist_ok=True)
    panels.raw_closes.to_csv(output_root / "eod_raw_close_panel.csv")
    _write_optional_panel(panels.raw_volumes, output_root / "eod_raw_volume_panel.csv")
    suspects = _split_like_returns(panels)
    suspects.to_csv(output_root / "unconfigured_split_like_returns.csv", index=False)
    if not suspects.empty:
        raise ValueError(
            "Split-like adjusted returns remain in the sector-ETF panel. "
            "Review unconfigured_split_like_returns.csv and add verified corporate actions."
        )
    panels.closes.to_csv(output_root / "eod_split_adjusted_close_panel.csv")
    _write_optional_panel(panels.volumes, output_root / "eod_split_adjusted_volume_panel.csv")
    _write_optional_panel(panels.dollar_volumes, output_root / "eod_dollar_volume_panel.csv")
    panels.returns.to_csv(output_root / "daily_split_adjusted_close_log_returns.csv")
    panels.split_adjustment_factors.to_csv(output_root / "split_adjustment_factors.csv")
    universe_frame().to_csv(output_root / "sector_assignments.csv", index=False)
    configured_split_frame().to_csv(output_root / "applied_split_events.csv", index=False)
    _write_summary(panels, paths, output_root)
    return panels


def _split_like_returns(panels: DailyEodPanels) -> pd.DataFrame:
    returns = panels.returns.stack().rename("log_return").reset_index()
    returns = returns.rename(columns={"level_1": "symbol"})
    returns["abs_log_return"] = returns["log_return"].abs()
    return returns.loc[
        returns["abs_log_return"] >= SPLIT_LIKE_ABS_LOG_RETURN
    ].sort_values("abs_log_return", ascending=False)


def _write_summary(
    panels: DailyEodPanels, paths: dict[str, Path], output_root: Path
) -> None:
    pd.DataFrame(
        {
            "symbol": SYMBOLS,
            "observations": [panels.closes[symbol].notna().sum() for symbol in SYMBOLS],
            "volume_observations": [
                int(panels.volumes[symbol].notna().sum()) if panels.volumes is not None else 0
                for symbol in SYMBOLS
            ],
            "raw_eod_path": [str(paths[symbol]) for symbol in SYMBOLS],
            "price_field": "split_adjusted_close",
            "volume_field": "split_adjusted_volume" if panels.volumes is not None else "",
            "split_adjusted": panels.split_adjusted,
            "dividend_adjusted": panels.dividend_adjusted,
            "corporate_action_adjusted": panels.corporate_action_adjusted,
        }
    ).to_csv(output_root / "ingestion_summary.csv", index=False)


def _write_optional_panel(panel: pd.DataFrame | None, path: Path) -> None:
    if panel is not None:
        panel.to_csv(path)


def _read_optional_cached_panel(
    path: Path, start_date: date, end_date: date
) -> pd.DataFrame | None:
    if not path.exists():
        return None
    panel = pd.read_csv(path, index_col="date", parse_dates=["date"])
    return panel.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]


def _records_from_cached_panels(
    raw_closes: pd.DataFrame, raw_volumes: pd.DataFrame | None
) -> pd.DataFrame:
    records = (
        raw_closes.rename_axis("created")
        .reset_index()
        .melt(id_vars="created", var_name="symbol", value_name="close")
        .dropna(subset=["close"])
    )
    if raw_volumes is None:
        return records
    volumes = (
        raw_volumes.rename_axis("created")
        .reset_index()
        .melt(id_vars="created", var_name="symbol", value_name="volume")
        .dropna(subset=["volume"])
    )
    return records.merge(volumes, on=["created", "symbol"], how="left")


if __name__ == "__main__":
    daily_panels = run()
    print(f"Wrote {len(daily_panels.closes)} daily rows for {len(STOCKS)} stocks.")
    print("Split discontinuities are checked; dividends remain unadjusted.")
