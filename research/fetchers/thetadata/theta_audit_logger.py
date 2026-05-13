from __future__ import annotations

"""CSV audit event writers for download runs."""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

DownloadStatus = Literal["saved", "skipped", "overwritten", "failed"]


@dataclass(frozen=True)
class DownloadAuditEvent:
    """Audit event payload for raw trade download outcomes."""

    timestamp_utc: str
    symbol: str
    trading_date: date
    action: DownloadStatus
    path: str | None
    rows: int | None
    error: str | None
    venue: str
    start_time: str
    end_time: str


@dataclass(frozen=True)
class TradeQuoteDownloadAuditEvent:
    """Audit event payload for raw trade-quote download outcomes."""

    timestamp_utc: str
    symbol: str
    trading_date: date
    action: DownloadStatus
    path: str | None
    rows: int | None
    error: str | None
    venue: str
    exclusive: bool
    start_time: str
    end_time: str


@dataclass(frozen=True)
class QuoteDownloadAuditEvent:
    """Audit event payload for raw quote download outcomes."""

    timestamp_utc: str
    symbol: str
    trading_date: date
    action: DownloadStatus
    path: str | None
    rows: int | None
    error: str | None
    venue: str
    interval: str
    start_time: str
    end_time: str


AuditEventLike = DownloadAuditEvent | TradeQuoteDownloadAuditEvent | QuoteDownloadAuditEvent


class DownloadAuditLogger:
    """Append-only event log writer."""

    def __init__(self, log_root: str | Path) -> None:
        self.log_root = Path(log_root)
        self.event_log_path = self.log_root / "download_events.csv"
        self.trade_quote_event_log_path = self.log_root / "download_trade_quote_events.csv"
        self.quote_event_log_path = self.log_root / "download_quote_events.csv"

        self.log_root.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: DownloadAuditEvent) -> None:
        """Append one trade-download event row."""
        self._append_event_csv(path=self.event_log_path, event=event)

    def log_trade_quote_event(self, event: TradeQuoteDownloadAuditEvent) -> None:
        """Append one trade-quote-download event row."""
        self._append_event_csv(path=self.trade_quote_event_log_path, event=event)

    def log_quote_event(self, event: QuoteDownloadAuditEvent) -> None:
        """Append one quote-download event row."""
        self._append_event_csv(path=self.quote_event_log_path, event=event)

    def _append_event_csv(self, path: Path, event: AuditEventLike) -> None:
        file_exists = path.exists()
        if isinstance(event, DownloadAuditEvent):
            fieldnames = [
                "timestamp_utc",
                "symbol",
                "trading_date",
                "action",
                "path",
                "rows",
                "error",
                "venue",
                "start_time",
                "end_time",
            ]
            row = {
                "timestamp_utc": event.timestamp_utc,
                "symbol": event.symbol,
                "trading_date": event.trading_date.isoformat(),
                "action": event.action,
                "path": event.path,
                "rows": event.rows,
                "error": event.error,
                "venue": event.venue,
                "start_time": event.start_time,
                "end_time": event.end_time,
            }
        elif isinstance(event, TradeQuoteDownloadAuditEvent):
            fieldnames = [
                "timestamp_utc",
                "symbol",
                "trading_date",
                "action",
                "path",
                "rows",
                "error",
                "venue",
                "exclusive",
                "start_time",
                "end_time",
            ]
            row = {
                "timestamp_utc": event.timestamp_utc,
                "symbol": event.symbol,
                "trading_date": event.trading_date.isoformat(),
                "action": event.action,
                "path": event.path,
                "rows": event.rows,
                "error": event.error,
                "venue": event.venue,
                "exclusive": event.exclusive,
                "start_time": event.start_time,
                "end_time": event.end_time,
            }
        else:
            fieldnames = [
                "timestamp_utc",
                "symbol",
                "trading_date",
                "action",
                "path",
                "rows",
                "error",
                "venue",
                "interval",
                "start_time",
                "end_time",
            ]
            row = {
                "timestamp_utc": event.timestamp_utc,
                "symbol": event.symbol,
                "trading_date": event.trading_date.isoformat(),
                "action": event.action,
                "path": event.path,
                "rows": event.rows,
                "error": event.error,
                "venue": event.venue,
                "interval": event.interval,
                "start_time": event.start_time,
                "end_time": event.end_time,
            }

        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
