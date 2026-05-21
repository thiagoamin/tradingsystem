from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.processing.returns_config import ReturnsConfig

QuoteVariable = Literal["mid", "spread_bps", "imbalance", "microprice", "microprice_pressure"]
QuoteVariablePanels = dict[str, pd.DataFrame]

DEFAULT_QUOTE_VARIABLES: tuple[QuoteVariable, ...] = (
    "mid",
    "spread_bps",
    "imbalance",
    "microprice",
    "microprice_pressure",
)


def build_quote_variables(
    config: ReturnsConfig,
    fetcher: ThetaDataFetcher,
    symbols: list[str],
    date_: date,
    start_time: time | None = None,
    end_time: time | None = None,
    variables: Sequence[QuoteVariable] = DEFAULT_QUOTE_VARIABLES,
) -> QuoteVariablePanels:
    """Build horizon-aligned quote variables from ThetaData NBBO quote snapshots.

    The implemented variables come from ``variables.pdf``:
    mid price, spread in basis points, bid/ask size imbalance, microprice, and
    microprice pressure. Returned panels share the same timestamp grid and symbol
    columns, making them directly alignable with ``build_returns`` output.
    """
    if not symbols:
        raise ValueError("symbols must be non-empty")
    if getattr(fetcher, "dataframe_type", None) != "pandas":
        raise ValueError("fetcher must be configured with dataframe_type='pandas'")
    if config.horizon.endswith("d"):
        raise NotImplementedError("daily horizons not supported for intraday quote variables")
    requested = _validate_variables(variables)
    window_start = start_time if start_time is not None else config.session_start
    window_end = end_time if end_time is not None else config.session_end
    if window_start >= window_end:
        raise ValueError("start_time must be strictly before end_time")

    grid = _build_grid(config=config, date_=date_, window_start=window_start, window_end=window_end)
    symbol_values = {name: [] for name in requested}
    normalized_symbols = [symbol.upper() for symbol in symbols]

    for symbol in normalized_symbols:
        values = _variables_for_symbol(
            config=config,
            fetcher=fetcher,
            symbol=symbol,
            date_=date_,
            grid=grid,
            start_time=window_start,
            end_time=window_end,
            requested=requested,
        )
        for name in requested:
            symbol_values[name].append(values[name])

    return {
        name: pd.concat(series_list, axis=1).reindex(columns=normalized_symbols)
        for name, series_list in symbol_values.items()
    }


def _validate_variables(variables: Sequence[QuoteVariable]) -> tuple[QuoteVariable, ...]:
    valid = set(DEFAULT_QUOTE_VARIABLES)
    unknown = sorted(set(variables) - valid)
    if unknown:
        raise ValueError(f"Unsupported quote variables: {unknown}. Supported values: {sorted(valid)}")
    if not variables:
        raise ValueError("variables must be non-empty")
    return tuple(dict.fromkeys(variables))


def _build_grid(config: ReturnsConfig, date_: date, window_start: time, window_end: time) -> pd.DatetimeIndex:
    today = date.today()
    effective_start = (datetime.combine(today, window_start) + timedelta(minutes=config.exclude_open_minutes)).time()
    effective_end = (datetime.combine(today, window_end) - timedelta(minutes=config.exclude_close_minutes)).time()
    if effective_start >= effective_end:
        raise ValueError("exclusion windows consume the entire requested window")
    tz = ZoneInfo(config.tz)
    start = pd.Timestamp(datetime.combine(date_, effective_start), tz=tz)
    end = pd.Timestamp(datetime.combine(date_, effective_end), tz=tz)
    grid = pd.date_range(start=start, end=end, freq=config.horizon_timedelta(), inclusive="both")
    grid.name = "timestamp"
    return grid


def _variables_for_symbol(
    config: ReturnsConfig,
    fetcher: ThetaDataFetcher,
    symbol: str,
    date_: date,
    grid: pd.DatetimeIndex,
    start_time: time,
    end_time: time,
    requested: tuple[QuoteVariable, ...],
) -> dict[QuoteVariable, pd.Series]:
    df_any = fetcher.fetch_stock_quotes(
        symbol=symbol,
        interval=config.horizon,
        date_=date_,
        start_time=start_time,
        end_time=end_time,
    )
    df = _as_pandas_df(df_any)
    if df.empty:
        return {name: _empty_series(grid, symbol) for name in requested}

    ts = _localize(cast(pd.Series, df["timestamp"]), ZoneInfo(config.tz))
    bid = cast(pd.Series, df["bid"]).astype(float)
    ask = cast(pd.Series, df["ask"]).astype(float)
    bid_size = cast(pd.Series, df["bid_size"]).astype(float)
    ask_size = cast(pd.Series, df["ask_size"]).astype(float)

    mid = (bid + ask) / 2.0
    spread = ask - bid
    size_sum = bid_size + ask_size
    spread_bps = _safe_divide(10_000.0 * spread, mid)
    imbalance = _safe_divide(bid_size - ask_size, size_sum)
    microprice = _safe_divide(ask * bid_size + bid * ask_size, size_sum)
    microprice_pressure = _safe_divide(microprice - mid, spread)

    raw: dict[QuoteVariable, pd.Series] = {
        "mid": pd.Series(mid.to_numpy(dtype=float), index=ts, name=symbol),
        "spread_bps": pd.Series(spread_bps, index=ts, name=symbol),
        "imbalance": pd.Series(imbalance, index=ts, name=symbol),
        "microprice": pd.Series(microprice, index=ts, name=symbol),
        "microprice_pressure": pd.Series(microprice_pressure, index=ts, name=symbol),
    }
    return {name: _dedupe_reindex(raw[name], grid, symbol) for name in requested}


def _as_pandas_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df
    raise TypeError("fetcher must return pandas DataFrames inside build_quote_variables")


def _localize(ts_raw: pd.Series, tz: ZoneInfo) -> pd.DatetimeIndex:
    ts_index = pd.DatetimeIndex(pd.to_datetime(ts_raw))
    if ts_index.tz is None:
        return ts_index.tz_localize(tz)
    return ts_index.tz_convert(tz)


def _safe_divide(numerator: pd.Series | np.ndarray, denominator: pd.Series | np.ndarray) -> np.ndarray:
    numerator_np = np.asarray(numerator, dtype=float)
    denominator_np = np.asarray(denominator, dtype=float)
    out = np.full_like(numerator_np, np.nan, dtype=float)
    np.divide(numerator_np, denominator_np, out=out, where=denominator_np != 0.0)
    out[~np.isfinite(out)] = np.nan
    return out


def _empty_series(index: pd.DatetimeIndex, symbol: str) -> pd.Series:
    return pd.Series(np.nan, index=index, name=symbol, dtype=float)


def _dedupe_reindex(series: pd.Series, grid: pd.DatetimeIndex, symbol: str) -> pd.Series:
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    out = series.reindex(grid)
    out.name = symbol
    return out
