from __future__ import annotations

"""Ingest ThetaData EOD closes and apply configured split adjustments.

ThetaData raw records remain saved unchanged. The derived research panel
corrects verified stock-split discontinuities; it is not dividend adjusted.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from research.fetchers.thetadata import ThetaDataEodIngestor
from research.tools.processing import DailyEodPanels, build_daily_eod_panels

from .configured_splits import RAW_CLOSE_SPLIT_EVENTS, split_event_audit_frame

TECH_STOCKS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AVGO",
    "AMD",
    "ADBE",
    "CRM",
    "CSCO",
    "INTC",
    "ORCL",
    "QCOM",
    "TXN",
]
FACTOR_ETFS = ["XLK", "SPY", "QQQ"]
SYMBOLS = TECH_STOCKS + FACTOR_ETFS
# ThetaData documents incomplete historical coverage for some ETFs before 2020.
START_DATE = date(2020, 1, 2)
END_DATE = date(2025, 12, 31)
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "theta_eod_ingestion"
)


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> DailyEodPanels:
    """Fetch raw ThetaData EOD records and write split-adjusted derived panels."""
    ingestor = ThetaDataEodIngestor(dataframe_type="pandas")
    result = ingestor.ingest(SYMBOLS, start_date=start_date, end_date=end_date, reuse_cache=True)
    panel_splits = tuple(event for event in RAW_CLOSE_SPLIT_EVENTS if event.symbol in SYMBOLS)
    panels = build_daily_eod_panels(
        result.records, TECH_STOCKS, FACTOR_ETFS, split_events=panel_splits
    )

    output_root.mkdir(parents=True, exist_ok=True)
    panels.raw_closes.to_csv(output_root / "eod_raw_close_panel.csv")
    _write_optional_panel(panels.raw_volumes, output_root / "eod_raw_volume_panel.csv")
    panels.closes.to_csv(output_root / "eod_close_panel.csv")
    panels.closes.to_csv(output_root / "eod_split_adjusted_close_panel.csv")
    _write_optional_panel(panels.volumes, output_root / "eod_split_adjusted_volume_panel.csv")
    _write_optional_panel(panels.dollar_volumes, output_root / "eod_dollar_volume_panel.csv")
    panels.split_adjustment_factors.to_csv(output_root / "split_adjustment_factors.csv")
    panels.returns.to_csv(output_root / "daily_close_log_returns.csv")
    panels.returns.to_csv(output_root / "daily_split_adjusted_close_log_returns.csv")
    split_event_audit_frame().to_csv(output_root / "applied_split_events.csv", index=False)
    _write_summary(panels, result.paths, output_root)
    return panels


def load_cached_panels(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> DailyEodPanels:
    """Load cached raw close output and reapply the current split schedule.

    This supports repeated modelling experiments without downloading an
    unchanged ThetaData history for every parameter comparison.
    """
    raw_path = output_root / "eod_raw_close_panel.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw EOD panel is absent; run ingestion first: {raw_path}")
    raw_closes = pd.read_csv(raw_path, index_col="date", parse_dates=["date"])
    raw_closes = raw_closes.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]
    raw_volumes = _read_optional_cached_panel(
        output_root / "eod_raw_volume_panel.csv", start_date=start_date, end_date=end_date
    )
    records = _records_from_cached_panels(raw_closes, raw_volumes)
    panel_splits = tuple(event for event in RAW_CLOSE_SPLIT_EVENTS if event.symbol in SYMBOLS)
    return build_daily_eod_panels(
        records, TECH_STOCKS, FACTOR_ETFS, split_events=panel_splits
    )


def _write_summary(
    panels: DailyEodPanels,
    paths: dict[str, Path],
    output_root: Path,
) -> None:
    summary = pd.DataFrame(
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
    )
    summary.to_csv(output_root / "ingestion_summary.csv", index=False)


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
    print(f"Wrote {len(daily_panels.closes)} split-adjusted daily close rows to {OUTPUT_ROOT}")
    print("Split discontinuities are adjusted; cash dividends remain unadjusted.")
