from __future__ import annotations

"""Runtime progress/retry logging helpers for bulk download runs."""

import logging

from fetchers_new.thetadata.theta_types import DatasetKind, DownloadResultLike, TradeDownloadJob


class DownloadRunLogger:
    """Thin wrapper around ``logging.Logger`` for consistent run log messages."""

    def __init__(self, log: logging.Logger) -> None:
        self._log = log

    def log_run_start(self, total_jobs: int, kind: DatasetKind) -> None:
        """Log run start with total jobs and dataset kind."""
        label = "trades" if kind == "trade" else "trade_quotes" if kind == "trade_quote" else "quotes"
        self._log.info("Running %d %s download jobs sequentially.", total_jobs, label)

    def log_retry(
        self,
        job: TradeDownloadJob,
        attempt: int,
        total_attempts: int,
        exc: Exception,
    ) -> None:
        """Log a retry attempt for a failed job attempt."""
        self._log.warning(
            "Retrying job symbol=%s date=%s attempt=%s/%s due to: %s",
            job.symbol,
            job.trading_date.isoformat(),
            attempt,
            total_attempts,
            exc,
        )

    def log_result(self, result: DownloadResultLike) -> None:
        """Log final per-job outcome."""
        if result.status in {"saved", "overwritten"}:
            self._log.info(
                "[%s] %s %s rows=%s path=%s",
                result.status,
                result.symbol,
                result.trading_date.isoformat(),
                result.rows,
                result.path,
            )
            return

        if result.status == "skipped":
            self._log.info(
                "[skipped] %s %s path=%s",
                result.symbol,
                result.trading_date.isoformat(),
                result.path,
            )
            return

        self._log.error(
            "[failed] %s %s error=%s",
            result.symbol,
            result.trading_date.isoformat(),
            result.error,
        )
