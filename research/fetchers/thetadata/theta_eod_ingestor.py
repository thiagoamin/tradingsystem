from __future__ import annotations

"""ThetaData end-of-day ingestion for daily research workflows."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl

from .theta_fetcher import DataFrameLike, ThetaDataFetcher
from .theta_storage import DEFAULT_THETADATA_ROOT, ThetaDataStorage


@dataclass(frozen=True)
class EodIngestionResult:
    """Raw ThetaData EOD records fetched for an experiment run."""

    records: pd.DataFrame
    paths: dict[str, Path]


class ThetaDataEodIngestor:
    """Fetch and persist ThetaData EOD records for stocks and ETFs.

    ThetaData's Python EOD endpoint returns generated OHLCV records rather than
    a declared split/dividend-adjusted close series. Any such adjustment belongs
    in an explicit downstream processing stage.
    """

    def __init__(
        self,
        data_root: str | Path = DEFAULT_THETADATA_ROOT,
        dataframe_type: Literal["pandas", "polars"] = "pandas",
    ) -> None:
        """Initialize a ThetaData fetcher and raw-record storage."""
        self.fetcher = ThetaDataFetcher(dataframe_type=dataframe_type)
        self.storage = ThetaDataStorage(data_root=data_root)

    def ingest(
        self,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
        reuse_cache: bool = False,
    ) -> EodIngestionResult:
        """Fetch and store EOD records for each symbol over one date range.

        Args:
            symbols: Stocks or ETFs to fetch.
            start_date: Inclusive range start.
            end_date: Inclusive range end.
            reuse_cache: If true, load an existing raw EOD parquet file when
                it covers the requested range; otherwise fetch from ThetaData.

        Returns:
            Concatenated records with an added ``symbol`` column and a map of
            saved raw parquet paths.

        Raises:
            ValueError: For an invalid range, empty symbol set, or empty response.
        """
        if start_date > end_date:
            raise ValueError("start_date must be less than or equal to end_date.")
        normalized_symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
        if not normalized_symbols:
            raise ValueError("symbols must be non-empty")

        records: list[pd.DataFrame] = []
        paths: dict[str, Path] = {}
        for symbol in normalized_symbols:
            cached = self._cached_frame(symbol, start_date, end_date) if reuse_cache else None
            if cached is None:
                fetched = self.fetcher.fetch_stock_eod(symbol=symbol, start_date=start_date, end_date=end_date)
                frame = self._as_pandas(fetched)
                paths[symbol] = self.storage.save_raw_eod(fetched, symbol=symbol, overwrite=True)
            else:
                frame = cached
                paths[symbol] = self.storage.raw_eod_path(symbol)
            if frame.empty:
                raise ValueError(f"No ThetaData EOD records returned for {symbol}.")
            frame.insert(0, "symbol", symbol)
            records.append(frame)
        return EodIngestionResult(records=pd.concat(records, ignore_index=True), paths=paths)

    def _cached_frame(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame | None:
        path = self.storage.raw_eod_path(symbol)
        if not path.exists():
            return None
        frame = pd.DataFrame(pl.read_parquet(path).to_dict(as_series=False))
        if frame.empty or "created" not in frame:
            return None
        dates = pd.to_datetime(frame["created"]).dt.date
        if dates.min() > start_date or dates.max() < end_date:
            return None
        return frame.loc[(dates >= start_date) & (dates <= end_date)].copy()

    @staticmethod
    def _as_pandas(df: DataFrameLike) -> pd.DataFrame:
        if isinstance(df, pd.DataFrame):
            return df.copy()
        if isinstance(df, pl.DataFrame):
            return pd.DataFrame(df.to_dict(as_series=False))
        raise TypeError(f"Unsupported EOD dataframe type: {type(df)!r}")
