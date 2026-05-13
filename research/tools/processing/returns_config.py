from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal, get_args

PriceSource = Literal["quote_mid", "trade_last", "trade_vwap"]
ReturnType = Literal["log", "simple"]


@dataclass(frozen=True)
class ReturnsConfig:
    """Immutable configuration for deterministic market return-series construction."""

    horizon: str
    price_source: PriceSource = "quote_mid"
    return_type: ReturnType = "log"
    session_start: time = time(9, 30)
    session_end: time = time(16, 0)
    exclude_open_minutes: int = 5
    exclude_close_minutes: int = 5
    tz: str = "America/New_York"

    def __post_init__(self) -> None:
        """Validate horizon, literals, session ordering, and exclusion settings."""
        self.horizon_timedelta()
        if self.price_source not in get_args(PriceSource):
            raise ValueError(f"Invalid price_source '{self.price_source}'. Expected one of: {list(get_args(PriceSource))}")
        if self.return_type not in get_args(ReturnType):
            raise ValueError(f"Invalid return_type '{self.return_type}'. Expected one of: {list(get_args(ReturnType))}")
        if self.session_start >= self.session_end:
            raise ValueError("session_start must be strictly before session_end")
        if self.exclude_open_minutes < 0 or self.exclude_close_minutes < 0:
            raise ValueError("exclusion minutes must be non-negative")
        start, end = self.effective_session()
        start_seconds = start.hour * 3600 + start.minute * 60 + start.second
        end_seconds = end.hour * 3600 + end.minute * 60 + end.second
        if end_seconds <= start_seconds:
            raise ValueError("exclusion windows consume the entire session; reduce exclude_open_minutes or exclude_close_minutes")

    def horizon_timedelta(self) -> timedelta:
        """Return the configured horizon as a timedelta or raise on invalid format."""
        match = re.fullmatch(r"(\d+)(s|m|h|d)", self.horizon)
        if not match:
            raise ValueError(
                f"Invalid horizon '{self.horizon}'. Expected format '<N><unit>' where unit is s, m, h, or d "
                "(e.g., '15s', '1m', '1h', '1d')."
            )
        value, unit = int(match.group(1)), match.group(2)
        if value <= 0:
            raise ValueError(f"Invalid horizon '{self.horizon}'. Horizon magnitude must be greater than zero.")
        kwargs = {"s": {"seconds": value}, "m": {"minutes": value}, "h": {"hours": value}, "d": {"days": value}}[unit]
        return timedelta(**kwargs)

    def effective_session(self) -> tuple[time, time]:
        """Return the session start/end times after open and close exclusions are applied."""
        today = date.today()
        effective_start = (datetime.combine(today, self.session_start) + timedelta(minutes=self.exclude_open_minutes)).time()
        effective_end = (datetime.combine(today, self.session_end) - timedelta(minutes=self.exclude_close_minutes)).time()
        return effective_start, effective_end
