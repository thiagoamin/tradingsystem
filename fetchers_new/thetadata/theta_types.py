from __future__ import annotations

"""Shared type aliases and immutable records for ThetaData download flows."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

DownloadStatus = Literal["saved", "skipped", "overwritten", "failed"]
Venue = Literal["nqb", "utp_cta"]
DataFrameType = Literal["pandas", "polars"]
QuoteInterval = Literal["tick", "10ms", "100ms", "500ms", "1s", "5s", "10s", "15s", "30s", "1m", "5m", "10m", "15m", "30m", "1h"]
DatasetKind = Literal["trade", "trade_quote", "quote"]


@dataclass(frozen=True)
class TradeDownloadJob:
    """Single symbol/date unit of work."""

    symbol: str
    trading_date: date


@dataclass(frozen=True)
class TradeDownloadResult:
    """Final outcome for one stock trade download job."""

    symbol: str
    trading_date: date
    status: DownloadStatus
    path: Path | None = None
    rows: int | None = None
    error: str | None = None
    venue: str | None = None
    start_time: str | None = None
    end_time: str | None = None


@dataclass(frozen=True)
class TradeQuoteDownloadResult:
    """Final outcome for one stock trade-quote download job."""

    symbol: str
    trading_date: date
    status: DownloadStatus
    path: Path | None = None
    rows: int | None = None
    error: str | None = None
    venue: str | None = None
    exclusive: bool | None = None
    start_time: str | None = None
    end_time: str | None = None


@dataclass(frozen=True)
class QuoteDownloadResult:
    """Final outcome for one stock quote download job."""

    symbol: str
    trading_date: date
    status: DownloadStatus
    path: Path | None = None
    rows: int | None = None
    error: str | None = None
    venue: str | None = None
    interval: str | None = None
    start_time: str | None = None
    end_time: str | None = None


DownloadResultLike = TradeDownloadResult | TradeQuoteDownloadResult | QuoteDownloadResult
