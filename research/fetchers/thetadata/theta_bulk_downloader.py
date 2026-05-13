from __future__ import annotations

"""Sequential bulk download orchestration for ThetaData trade datasets."""

import logging
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Sequence, cast

import pandas as pd
import polars as pl

from .theta_audit_logger import DownloadAuditEvent, DownloadAuditLogger, QuoteDownloadAuditEvent, TradeQuoteDownloadAuditEvent
from .theta_fetcher import DataFrameLike, ThetaDataFetcher
from .theta_runtime_logger import DownloadRunLogger
from .theta_storage import DEFAULT_THETADATA_ROOT, ThetaDataStorage
from .theta_types import (
    DataFrameType,
    DatasetKind,
    DownloadResultLike,
    DownloadStatus,
    QuoteDownloadResult,
    QuoteInterval,
    TradeDownloadJob,
    TradeDownloadResult,
    TradeQuoteDownloadResult,
    Venue,
)

logger = logging.getLogger(__name__)


class ThetaDataBulkDownloader:
    """Coordinate job building, fetching, persistence, and audit logging."""

    _VALID_VENUES = {"nqb", "utp_cta"}

    def __init__(self, data_root: str | Path = DEFAULT_THETADATA_ROOT, dataframe_type: DataFrameType = "polars", default_venue: Venue = "utp_cta", max_retries: int = 2, retry_sleep_seconds: float = 2.0) -> None:
        """Initialize downloader configuration and collaborators."""
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._validate_venue(default_venue)

        self.data_root = Path(data_root)
        self.dataframe_type: DataFrameType = dataframe_type
        self.default_venue = default_venue
        self.max_retries = max_retries
        self.retry_sleep_seconds = retry_sleep_seconds

        self.storage = ThetaDataStorage(data_root=self.data_root)
        self.audit_logger = DownloadAuditLogger(log_root=self.data_root / "thetadata_logs")
        self.run_logger = DownloadRunLogger(logger)

    def expected_raw_path(self, symbol: str, trading_date: date) -> Path:
        """Return expected raw trade parquet path for one symbol/date."""
        return self.storage.raw_trades_path(symbol, trading_date)

    def expected_raw_trade_quotes_path(self, symbol: str, trading_date: date) -> Path:
        """Return expected raw trade-quote parquet path for one symbol/date."""
        return self.storage.raw_trade_quotes_path(symbol, trading_date)

    def expected_raw_quotes_path(self, symbol: str, trading_date: date) -> Path:
        """Return expected raw quote parquet path for one symbol/date."""
        return self.storage.raw_quotes_path(symbol, trading_date)

    def iter_trading_dates(self, start_date: date, end_date: date) -> list[date]:
        """Expand inclusive date range to weekdays (weekend-filtered only)."""
        if start_date > end_date:
            raise ValueError("start_date must be less than or equal to end_date.")

        dates: list[date] = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                dates.append(current)
            current += timedelta(days=1)
        return dates

    def build_jobs(self, symbols: list[str], start_date: date, end_date: date) -> list[TradeDownloadJob]:
        """Build one job per (symbol, trading_date) pair."""
        if not symbols:
            raise ValueError("symbols list cannot be empty.")

        unique_symbols = self._normalize_symbols(symbols)
        trading_dates = self.iter_trading_dates(start_date=start_date, end_date=end_date)
        jobs: list[TradeDownloadJob] = []
        for symbol in unique_symbols:
            for trading_date in trading_dates:
                jobs.append(TradeDownloadJob(symbol=symbol, trading_date=trading_date))
        return jobs

    def download_stock_trades(self, symbols: list[str], start_date: date, end_date: date, start_time: time = time(9, 30), end_time: time = time(16, 0), venue: Venue | None = None, overwrite: bool = False) -> list[TradeDownloadResult]:
        """Download raw stock trades and return per-job results."""
        results = self._download_jobs(kind="trade", symbols=symbols, start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time, venue=venue, overwrite=overwrite, exclusive=None, interval=None)
        return [cast(TradeDownloadResult, result) for result in results]

    def download_stock_trade_quotes(self, symbols: list[str], start_date: date, end_date: date, start_time: time = time(9, 30), end_time: time = time(16, 0), exclusive: bool = True, venue: Venue | None = None, overwrite: bool = False) -> list[TradeQuoteDownloadResult]:
        """Download raw stock trade-quote records and return per-job results."""
        results = self._download_jobs(kind="trade_quote", symbols=symbols, start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time, venue=venue, overwrite=overwrite, exclusive=exclusive, interval=None)
        return [cast(TradeQuoteDownloadResult, result) for result in results]

    def download_stock_quotes(self, symbols: list[str], start_date: date, end_date: date, interval: QuoteInterval = "500ms", start_time: time = time(9, 30), end_time: time = time(16, 0), venue: Venue | None = None, overwrite: bool = False) -> list[QuoteDownloadResult]:
        """Download raw stock quote records and return per-job results."""
        results = self._download_jobs(kind="quote", symbols=symbols, start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time, venue=venue, overwrite=overwrite, exclusive=None, interval=interval)
        return [cast(QuoteDownloadResult, result) for result in results]

    def summarize_results(self, results: Sequence[DownloadResultLike]) -> dict[str, int]:
        """Count saved/skipped/overwritten/failed outcomes."""
        summary = {"saved": 0, "skipped": 0, "overwritten": 0, "failed": 0}
        for result in results:
            summary[result.status] += 1
        return summary

    def _download_jobs(self, kind: DatasetKind, symbols: list[str], start_date: date, end_date: date, start_time: time, end_time: time, venue: Venue | None, overwrite: bool, exclusive: bool | None, interval: QuoteInterval | None) -> list[DownloadResultLike]:
        jobs = self.build_jobs(symbols=symbols, start_date=start_date, end_date=end_date)
        self.run_logger.log_run_start(len(jobs), kind)
        results: list[DownloadResultLike] = []
        for job in jobs:
            result = self._download_one_job(kind=kind, job=job, start_time=start_time, end_time=end_time, venue=venue, overwrite=overwrite, exclusive=exclusive, interval=interval)
            results.append(result)
        return results

    def _download_one_job(self, kind: DatasetKind, job: TradeDownloadJob, start_time: time, end_time: time, venue: Venue | None, overwrite: bool, exclusive: bool | None, interval: QuoteInterval | None) -> DownloadResultLike:
        selected_venue = self._validate_venue(venue or self.default_venue)
        expected_path = self._expected_path(kind=kind, symbol=job.symbol, trading_date=job.trading_date)
        existed_before = expected_path.exists()

        if existed_before and not overwrite:
            result = self._build_result(kind=kind, job=job, status="skipped", venue=selected_venue, start_time=start_time, end_time=end_time, path=expected_path, exclusive=exclusive, interval=interval)
            return self._finalize_result(kind=kind, result=result, venue=selected_venue, start_time=start_time, end_time=end_time, exclusive=exclusive, interval=interval)

        result = self._attempt_with_retries(kind=kind, job=job, venue=selected_venue, start_time=start_time, end_time=end_time, overwrite=overwrite, expected_path=expected_path, existed_before=existed_before, exclusive=exclusive, interval=interval)
        return self._finalize_result(kind=kind, result=result, venue=selected_venue, start_time=start_time, end_time=end_time, exclusive=exclusive, interval=interval)

    def _attempt_with_retries(self, kind: DatasetKind, job: TradeDownloadJob, venue: Venue, start_time: time, end_time: time, overwrite: bool, expected_path: Path, existed_before: bool, exclusive: bool | None, interval: QuoteInterval | None) -> DownloadResultLike:
        total_attempts = self.max_retries + 1
        for attempt_index in range(total_attempts):
            try:
                df = self._fetch_df(kind=kind, job=job, venue=venue, start_time=start_time, end_time=end_time, exclusive=exclusive, interval=interval)
                return self._persist_result(kind=kind, job=job, df=df, venue=venue, start_time=start_time, end_time=end_time, overwrite=overwrite, expected_path=expected_path, existed_before=existed_before, exclusive=exclusive, interval=interval)
            except Exception as exc:  # noqa: BLE001
                if attempt_index == total_attempts - 1:
                    return self._build_result(kind=kind, job=job, status="failed", venue=venue, start_time=start_time, end_time=end_time, path=expected_path, error=str(exc), exclusive=exclusive, interval=interval)
                self.run_logger.log_retry(job=job, attempt=attempt_index + 1, total_attempts=total_attempts, exc=exc)
                time_module.sleep(self.retry_sleep_seconds)

        return self._build_result(kind=kind, job=job, status="failed", venue=venue, start_time=start_time, end_time=end_time, path=expected_path, error="Unknown failure while downloading job.", exclusive=exclusive, interval=interval)

    def _fetch_df(self, kind: DatasetKind, job: TradeDownloadJob, venue: Venue, start_time: time, end_time: time, exclusive: bool | None, interval: QuoteInterval | None) -> DataFrameLike:
        fetcher = ThetaDataFetcher(dataframe_type=self.dataframe_type, default_venue=self.default_venue)
        try:
            if kind == "trade":
                return fetcher.fetch_stock_trades(symbol=job.symbol, date_=job.trading_date, start_time=start_time, end_time=end_time, venue=venue)
            if kind == "trade_quote":
                return fetcher.fetch_stock_trade_quotes(symbol=job.symbol, date_=job.trading_date, start_time=start_time, end_time=end_time, exclusive=True if exclusive is None else exclusive, venue=venue)
            return fetcher.fetch_stock_quotes(symbol=job.symbol, date_=job.trading_date, interval="500ms" if interval is None else interval, start_time=start_time, end_time=end_time, venue=venue)
        finally:
            close_method = getattr(fetcher.client, "close", None)
            if callable(close_method):
                close_method()

    def _persist_result(self, kind: DatasetKind, job: TradeDownloadJob, df: DataFrameLike, venue: Venue, start_time: time, end_time: time, overwrite: bool, expected_path: Path, existed_before: bool, exclusive: bool | None, interval: QuoteInterval | None) -> DownloadResultLike:
        rows = self._row_count(df)
        if rows == 0:
            return self._build_result(kind=kind, job=job, status="skipped", venue=venue, start_time=start_time, end_time=end_time, path=expected_path, rows=0, error="no_data", exclusive=exclusive, interval=interval)

        path = self._save_df(kind=kind, df=df, symbol=job.symbol, trading_date=job.trading_date, overwrite=overwrite)
        status: DownloadStatus = "overwritten" if existed_before and overwrite else "saved"
        return self._build_result(kind=kind, job=job, status=status, venue=venue, start_time=start_time, end_time=end_time, path=path, rows=rows, exclusive=exclusive, interval=interval)

    def _save_df(self, kind: DatasetKind, df: DataFrameLike, symbol: str, trading_date: date, overwrite: bool) -> Path:
        if kind == "trade":
            return self.storage.save_raw_trades(df=df, symbol=symbol, trading_date=trading_date, overwrite=overwrite)
        if kind == "trade_quote":
            return self.storage.save_raw_trade_quotes(df=df, symbol=symbol, trading_date=trading_date, overwrite=overwrite)
        return self.storage.save_raw_quotes(df=df, symbol=symbol, trading_date=trading_date, overwrite=overwrite)

    def _expected_path(self, kind: DatasetKind, symbol: str, trading_date: date) -> Path:
        if kind == "trade":
            return self.storage.raw_trades_path(symbol, trading_date)
        if kind == "trade_quote":
            return self.storage.raw_trade_quotes_path(symbol, trading_date)
        return self.storage.raw_quotes_path(symbol, trading_date)

    def _build_result(self, kind: DatasetKind, job: TradeDownloadJob, status: DownloadStatus, venue: Venue, start_time: time, end_time: time, path: Path | None = None, rows: int | None = None, error: str | None = None, exclusive: bool | None = None, interval: QuoteInterval | None = None) -> DownloadResultLike:
        if kind == "trade":
            return TradeDownloadResult(symbol=job.symbol, trading_date=job.trading_date, status=status, path=path, rows=rows, error=error, venue=venue, start_time=start_time.isoformat(), end_time=end_time.isoformat())
        if kind == "trade_quote":
            return TradeQuoteDownloadResult(symbol=job.symbol, trading_date=job.trading_date, status=status, path=path, rows=rows, error=error, venue=venue, exclusive=True if exclusive is None else exclusive, start_time=start_time.isoformat(), end_time=end_time.isoformat())
        return QuoteDownloadResult(symbol=job.symbol, trading_date=job.trading_date, status=status, path=path, rows=rows, error=error, venue=venue, interval="500ms" if interval is None else interval, start_time=start_time.isoformat(), end_time=end_time.isoformat())

    def _finalize_result(self, kind: DatasetKind, result: DownloadResultLike, venue: Venue, start_time: time, end_time: time, exclusive: bool | None, interval: QuoteInterval | None) -> DownloadResultLike:
        self._log_audit(kind=kind, result=result, venue=venue, start_time=start_time, end_time=end_time, exclusive=exclusive, interval=interval)
        self.run_logger.log_result(result)
        return result

    def _log_audit(self, kind: DatasetKind, result: DownloadResultLike, venue: Venue, start_time: time, end_time: time, exclusive: bool | None, interval: QuoteInterval | None) -> None:
        if kind == "trade":
            trade_result = cast(TradeDownloadResult, result)
            self.audit_logger.log_event(
                DownloadAuditEvent(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    symbol=trade_result.symbol,
                    trading_date=trade_result.trading_date,
                    action=trade_result.status,
                    path=str(trade_result.path) if trade_result.path is not None else None,
                    rows=trade_result.rows,
                    error=trade_result.error,
                    venue=venue,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                )
            )
            return

        if kind == "quote":
            quote_result = cast(QuoteDownloadResult, result)
            self.audit_logger.log_quote_event(
                QuoteDownloadAuditEvent(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    symbol=quote_result.symbol,
                    trading_date=quote_result.trading_date,
                    action=quote_result.status,
                    path=str(quote_result.path) if quote_result.path is not None else None,
                    rows=quote_result.rows,
                    error=quote_result.error,
                    venue=venue,
                    interval="500ms" if interval is None else interval,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                )
            )
            return

        quote_result = cast(TradeQuoteDownloadResult, result)
        self.audit_logger.log_trade_quote_event(
            TradeQuoteDownloadAuditEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                symbol=quote_result.symbol,
                trading_date=quote_result.trading_date,
                action=quote_result.status,
                path=str(quote_result.path) if quote_result.path is not None else None,
                rows=quote_result.rows,
                error=quote_result.error,
                venue=venue,
                exclusive=True if exclusive is None else exclusive,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )
        )

    def _validate_venue(self, venue: str) -> Venue:
        if venue not in self._VALID_VENUES:
            raise ValueError(f"Invalid venue '{venue}'. Expected one of: {sorted(self._VALID_VENUES)}")
        return cast(Venue, venue)

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        unique_symbols: list[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            normalized = symbol.upper()
            if normalized not in seen:
                seen.add(normalized)
                unique_symbols.append(normalized)
        return unique_symbols

    def _row_count(self, df: DataFrameLike) -> int:
        if isinstance(df, pl.DataFrame):
            return df.height
        if isinstance(df, pd.DataFrame):
            return len(df)
        raise TypeError(f"Unsupported dataframe type for row counting: {type(df)!r}")
