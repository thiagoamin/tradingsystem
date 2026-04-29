from __future__ import annotations

from datetime import date, time
from typing import Any, Literal

import pandas as pd
import polars as pl
from thetadata.client import ThetaClient

DataFrameLike = pd.DataFrame | pl.DataFrame


class ThetaDataFetcher:
    """Small wrapper around ThetaClient for stock historical data pulls."""

    _VALID_VENUES = {"nqb", "utp_cta"}
    _VALID_QUOTE_INTERVALS = {"tick", "10ms", "100ms", "500ms", "1s", "5s", "10s", "15s", "30s", "1m", "5m", "10m", "15m", "30m", "1h"}
    _SUB_MINUTE_INTERVALS = {"tick", "10ms", "100ms", "500ms", "1s", "5s", "10s", "15s", "30s"}

    def __init__(
        self,
        dataframe_type: Literal["pandas", "polars"] = "pandas",
        default_venue: str = "utp_cta",
    ) -> None:
        """Initialize the ThetaData stock-trade fetcher.

        Reference:
        https://docs.thetadata.us/operations_python/stock_history_trade.html

        Args:
            dataframe_type: Response format expected from ThetaData
                (``"pandas"`` or ``"polars"``).
            default_venue: Default trade venue ("nqb" or "utp_cta").
        """
        self.dataframe_type = dataframe_type
        self.client = ThetaClient(dataframe_type=dataframe_type)
        self.default_venue = self._validate_venue(default_venue)

    def fetch_stock_trades(
        self,
        symbol: str,
        date_: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        start_time: time = time(9, 30),
        end_time: time = time(16, 0),
        venue: str | None = None,
    ) -> DataFrameLike:
        """Fetch raw historical trades for a single stock symbol.

        Wraps ``ThetaClient.stock_history_trade(...)``.

        Reference:
        https://docs.thetadata.us/operations_python/stock_history_trade.html

        Args:
            symbol: Stock symbol (normalized to uppercase).
            date_: Single trade date. Use this or a date range.
            start_date: Range start date (inclusive).
            end_date: Range end date (inclusive).
            start_time: Intraday start time filter (default ``09:30``).
            end_time: Intraday end time filter (default ``16:00``).
            venue: Optional venue override; defaults to ``self.default_venue``.

        Returns:
            A pandas or polars DataFrame, depending on ``dataframe_type``.
            If ThetaData reports no data for the request, an empty dataframe is returned.

        Raises:
            ValueError: Invalid venue or invalid date/date-range arguments.
            TypeError: Unexpected ThetaData response type.
        """
        symbol = symbol.upper()
        venue_to_use = self._validate_venue(venue or self.default_venue)
        date_args = self._build_date_args(date_=date_, start_date=start_date, end_date=end_date)

        try:
            result = self.client.stock_history_trade(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                venue=venue_to_use,
                **date_args,
            )
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ == "NoDataFoundError":
                return self._empty_dataframe()
            raise

        return self._validate_result(result)

    def fetch_stock_trade_quotes(
        self,
        symbol: str,
        date_: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        start_time: time = time(9, 30),
        end_time: time = time(16, 0),
        exclusive: bool = True,
        venue: str | None = None,
    ) -> DataFrameLike:
        """Fetch trade+quote records for a single stock symbol.

        Wraps ``ThetaClient.stock_history_trade_quote(...)``.

        Reference:
        https://docs.thetadata.us/operations_python/stock_history_trade_quote.html

        Args:
            symbol: Stock symbol (normalized to uppercase).
            date_: Single date. Use this or a date range.
            start_date: Range start date (inclusive).
            end_date: Range end date (inclusive).
            start_time: Intraday start time filter (default ``09:30``).
            end_time: Intraday end time filter (default ``16:00``).
            exclusive: If true, matches quote timestamp strictly < trade timestamp.
            venue: Optional venue override; defaults to ``self.default_venue``.

        Returns:
            A pandas or polars DataFrame; empty dataframe when no data is returned.
        """
        symbol = symbol.upper()
        venue_to_use = self._validate_venue(venue or self.default_venue)
        date_args = self._build_date_args(date_=date_, start_date=start_date, end_date=end_date)

        try:
            result = self.client.stock_history_trade_quote(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                exclusive=exclusive,
                venue=venue_to_use,
                **date_args,
            )
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ == "NoDataFoundError":
                return self._empty_dataframe()
            raise

        return self._validate_result(result)

    def fetch_stock_quotes(
        self,
        symbol: str,
        interval: str = "500ms",
        date_: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        start_time: time = time(9, 30),
        end_time: time = time(16, 0),
        venue: str | None = None,
    ) -> DataFrameLike:
        """Fetch NBBO quote history for a single stock symbol.

        Wraps ``ThetaClient.stock_history_quote(...)``.

        Reference:
        https://docs.thetadata.us/operations_python/stock_history_quote.html
        """
        symbol = symbol.upper()
        interval_to_use = self._validate_quote_interval(interval)
        venue_to_use = self._validate_venue(venue or self.default_venue)
        date_args = self._build_date_args(date_=date_, start_date=start_date, end_date=end_date)
        self._validate_quote_interval_window(interval=interval_to_use, date_=date_, start_date=start_date, end_date=end_date)

        try:
            result = self.client.stock_history_quote(
                symbol=symbol,
                interval=interval_to_use,
                start_time=start_time,
                end_time=end_time,
                venue=venue_to_use,
                **date_args,
            )
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ == "NoDataFoundError":
                return self._empty_dataframe()
            raise

        return self._validate_result(result)

    def _validate_venue(self, venue: str) -> str:
        """Validate venue against supported ThetaData stock-trade venues."""
        if venue not in self._VALID_VENUES:
            raise ValueError(
                f"Invalid venue '{venue}'. Expected one of: "
                f"{sorted(self._VALID_VENUES)}"
            )
        return venue

    def _validate_quote_interval(self, interval: str) -> str:
        if interval not in self._VALID_QUOTE_INTERVALS:
            raise ValueError(
                f"Invalid interval '{interval}'. Expected one of: "
                f"{sorted(self._VALID_QUOTE_INTERVALS)}"
            )
        return interval

    def _validate_quote_interval_window(
        self,
        interval: str,
        date_: date | None,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        if interval not in self._SUB_MINUTE_INTERVALS:
            return
        if date_ is not None:
            return
        if start_date is not None and end_date is not None and start_date == end_date:
            return
        raise ValueError(
            "Intervals below 1m require a single-day request. "
            "Use date_ or set start_date == end_date."
        )

    def _build_date_args(
        self,
        date_: date | None,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, date]:
        """Validate date inputs and build ThetaData date keyword arguments."""
        has_single_date = date_ is not None
        has_date_range = start_date is not None and end_date is not None
        has_partial_range = (start_date is None) ^ (end_date is None)

        if has_partial_range or has_single_date == has_date_range:
            raise ValueError("Provide either date_ OR both start_date and end_date.")

        if has_single_date:
            if date_ is None:
                raise ValueError("date_ cannot be None when date mode is selected.")
            return {"date": date_}
        if start_date is None or end_date is None:
            raise ValueError("Both start_date and end_date are required for range mode.")
        if start_date > end_date:
            raise ValueError("start_date must be less than or equal to end_date.")
        return {"start_date": start_date, "end_date": end_date}

    def _validate_result(self, result: Any) -> DataFrameLike:
        """Validate that result is a pandas/polars DataFrame as expected."""
        if isinstance(result, pd.DataFrame):
            return result

        if isinstance(result, pl.DataFrame):
            return result

        raise TypeError(
            "Unexpected ThetaData response type. Expected pandas or polars DataFrame, "
            f"got {type(result)!r}."
        )

    def _empty_dataframe(self) -> DataFrameLike:
        """Return an empty dataframe matching configured dataframe_type."""
        if self.dataframe_type == "polars":
            return pl.DataFrame()
        return pd.DataFrame()
