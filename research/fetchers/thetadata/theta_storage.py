from __future__ import annotations

"""Filesystem pathing and Parquet persistence for raw ThetaData datasets."""

from datetime import date
from pathlib import Path

import pandas as pd
import polars as pl

from .theta_fetcher import DataFrameLike
from .theta_types import DatasetKind

DEFAULT_THETADATA_ROOT = Path("research") / "raw_data_cache" / "thetadata"


class ThetaDataStorage:
    """Map symbol/date records to parquet paths and write parquet files."""

    def __init__(self, data_root: str | Path = DEFAULT_THETADATA_ROOT) -> None:
        """Initialize storage rooted at ``data_root``."""
        self.data_root = Path(data_root)

    def raw_trades_path(self, symbol: str, trading_date: date) -> Path:
        """Return canonical parquet path for raw trade records."""
        return self._raw_path(kind="trade", symbol=symbol, trading_date=trading_date)

    def raw_trade_quotes_path(self, symbol: str, trading_date: date) -> Path:
        """Return canonical parquet path for raw trade-quote records."""
        return self._raw_path(kind="trade_quote", symbol=symbol, trading_date=trading_date)

    def raw_quotes_path(self, symbol: str, trading_date: date) -> Path:
        """Return canonical parquet path for raw quote records."""
        return self._raw_path(kind="quote", symbol=symbol, trading_date=trading_date)

    def raw_eod_path(self, symbol: str) -> Path:
        """Return canonical parquet path for a raw EOD history pull."""
        return self.data_root / "thetadata_raw" / "eod" / f"symbol={symbol.upper()}" / "part.parquet"

    def exists_raw_trades(self, symbol: str, trading_date: date) -> bool:
        return self.raw_trades_path(symbol, trading_date).exists()

    def exists_raw_trade_quotes(self, symbol: str, trading_date: date) -> bool:
        return self.raw_trade_quotes_path(symbol, trading_date).exists()

    def exists_raw_quotes(self, symbol: str, trading_date: date) -> bool:
        return self.raw_quotes_path(symbol, trading_date).exists()

    def exists_raw_eod(self, symbol: str) -> bool:
        """Return whether EOD records have been cached for ``symbol``."""
        return self.raw_eod_path(symbol).exists()

    def save_raw_trades(
        self,
        df: DataFrameLike,
        symbol: str,
        trading_date: date,
        overwrite: bool = False,
    ) -> Path:
        """Persist raw trade dataframe as parquet and return saved path."""
        path = self.raw_trades_path(symbol, trading_date)
        return self._write_parquet(df=df, path=path, overwrite=overwrite)

    def save_raw_trade_quotes(
        self,
        df: DataFrameLike,
        symbol: str,
        trading_date: date,
        overwrite: bool = False,
    ) -> Path:
        """Persist raw trade-quote dataframe as parquet and return saved path."""
        path = self.raw_trade_quotes_path(symbol, trading_date)
        return self._write_parquet(df=df, path=path, overwrite=overwrite)

    def save_raw_quotes(
        self,
        df: DataFrameLike,
        symbol: str,
        trading_date: date,
        overwrite: bool = False,
    ) -> Path:
        """Persist raw quote dataframe as parquet and return saved path."""
        path = self.raw_quotes_path(symbol, trading_date)
        return self._write_parquet(df=df, path=path, overwrite=overwrite)

    def save_raw_eod(self, df: DataFrameLike, symbol: str, overwrite: bool = False) -> Path:
        """Persist a raw ThetaData EOD history response as parquet."""
        return self._write_parquet(df=df, path=self.raw_eod_path(symbol), overwrite=overwrite)

    def _raw_path(
        self,
        kind: DatasetKind,
        symbol: str,
        trading_date: date,
    ) -> Path:
        leaf = "trades" if kind == "trade" else "trade_quotes" if kind == "trade_quote" else "quotes"
        return (
            self.data_root
            / "thetadata_raw"
            / leaf
            / f"symbol={symbol.upper()}"
            / f"date={trading_date.isoformat()}"
            / "part.parquet"
        )

    def _write_parquet(
        self,
        df: DataFrameLike,
        path: Path,
        overwrite: bool,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and not overwrite:
            raise FileExistsError(f"Raw parquet file already exists: {path}")

        if isinstance(df, pl.DataFrame):
            df.write_parquet(path, compression="zstd", compression_level=9)
            return path

        if isinstance(df, pd.DataFrame):
            pl.DataFrame({str(column): df[column].to_list() for column in df.columns}).write_parquet(
                path, compression="zstd", compression_level=9
            )
            return path

        raise TypeError(f"Unsupported dataframe type for parquet saving: {type(df)!r}")
