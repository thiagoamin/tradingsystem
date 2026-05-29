from __future__ import annotations

"""Data source that reads pre-saved raw EOD panels from disk."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.tools.data.base import DataSource, PanelRequest
from research.tools.processing import DailyEodPanels, build_daily_eod_panels


class CachedPanelSource(DataSource):
    """Reads ``eod_raw_close_panel.csv`` (and optional volume panel) from a
    cache directory and re-runs ``build_daily_eod_panels`` to apply the
    current split schedule.

    This is the source of choice during research iteration: the underlying
    ThetaData fetch is run once via ``ThetaPanelSource``, and every later
    experiment can rebuild panels in seconds without network access.
    """

    def __init__(self, cache_root: Path):
        """Args:
            cache_root: Directory containing the ingestion output.
        """
        self._cache_root = Path(cache_root)

    @property
    def cache_root(self) -> Path:
        return self._cache_root

    def get_panels(self, request: PanelRequest) -> DailyEodPanels:
        raw_close_path = self._cache_root / "eod_raw_close_panel.csv"
        if not raw_close_path.exists():
            raise FileNotFoundError(
                f"Cached raw close panel not found at {raw_close_path}. "
                "Run a ThetaPanelSource (or its ingestion script) first."
            )
        raw_closes = self._read_panel(raw_close_path, request.start_date, request.end_date)
        raw_volumes = self._maybe_read_volume_panel(request.start_date, request.end_date)
        records = _records_from_panels(raw_closes, raw_volumes)
        return build_daily_eod_panels(
            records,
            list(request.universe.stocks),
            list(request.universe.factor_etfs),
            split_events=request.universe.applicable_splits,
        )

    def _maybe_read_volume_panel(self, start_date: date, end_date: date) -> pd.DataFrame | None:
        volume_path = self._cache_root / "eod_raw_volume_panel.csv"
        if not volume_path.exists():
            return None
        return self._read_panel(volume_path, start_date, end_date)

    @staticmethod
    def _read_panel(path: Path, start_date: date, end_date: date) -> pd.DataFrame:
        panel = pd.read_csv(path, index_col="date", parse_dates=["date"])
        return panel.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]


def _records_from_panels(raw_closes: pd.DataFrame, raw_volumes: pd.DataFrame | None) -> pd.DataFrame:
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
