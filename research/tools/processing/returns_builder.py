from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.processing.returns_config import ReturnsConfig


def build_returns(
    config: ReturnsConfig,
    fetcher: ThetaDataFetcher,
    symbols: list[str],
    date_: date,
    start_time: time | None = None,
    end_time: time | None = None,
) -> pd.DataFrame:
    """Build horizon-aligned returns for one date from raw ThetaData trades or quotes.

    Args:
        config: Return-construction configuration.
        fetcher: ThetaData fetcher configured to return pandas DataFrames.
        symbols: Universe of symbols; columns preserve this order after upper-casing.
        date_: Trading date to process.
        start_time: Optional requested window start before config exclusions.
        end_time: Optional requested window end before config exclusions.

    Returns:
        A timezone-aware DataFrame indexed by aligned bar timestamps with one return column per symbol.

    Raises:
        ValueError: Invalid symbols, horizon, fetcher type, or requested time window.
        NotImplementedError: Daily horizons and unsupported methodological branches.
    """
    valid_intervals = {"tick", "10ms", "100ms", "500ms", "1s", "5s", "10s", "15s", "30s", "1m", "5m", "10m", "15m", "30m", "1h"}
    if not symbols:
        raise ValueError("symbols must be non-empty")
    if getattr(fetcher, "dataframe_type", None) != "pandas":
        raise ValueError("fetcher must be configured with dataframe_type='pandas'")
    if config.horizon.endswith("d"):
        raise NotImplementedError("daily horizons not supported in v1 (fetcher endpoints are intraday only)")
    if config.horizon not in valid_intervals:
        raise ValueError(f"Unsupported horizon '{config.horizon}'. Supported values: {sorted(valid_intervals)}")

    window_start = start_time if start_time is not None else config.session_start
    window_end = end_time if end_time is not None else config.session_end
    if window_start >= window_end:
        raise ValueError("start_time must be strictly before end_time")

    today = date.today()
    effective_start_t = (datetime.combine(today, window_start) + timedelta(minutes=config.exclude_open_minutes)).time()
    effective_end_t = (datetime.combine(today, window_end) - timedelta(minutes=config.exclude_close_minutes)).time()
    if effective_start_t >= effective_end_t:
        raise ValueError("exclusion windows consume the entire requested window; reduce exclude_*_minutes or widen start_time/end_time")

    tz = ZoneInfo(config.tz)
    effective_start_dt = pd.Timestamp(datetime.combine(date_, effective_start_t), tz=tz)
    effective_end_dt = pd.Timestamp(datetime.combine(date_, effective_end_t), tz=tz)
    grid = pd.date_range(start=effective_start_dt, end=effective_end_dt, freq=config.horizon_timedelta(), inclusive="both")
    grid.name = "timestamp"
    horizon_td = config.horizon_timedelta()

    def _localize(ts_raw: pd.Series) -> pd.DatetimeIndex:
        ts_index = pd.DatetimeIndex(pd.to_datetime(ts_raw))
        if ts_index.tz is None:
            return ts_index.tz_localize(tz)
        return ts_index.tz_convert(tz)

    def _empty(symbol: str) -> pd.Series:
        return pd.Series(np.nan, index=grid, name=symbol, dtype=float)

    def _as_pandas_df(df: Any) -> pd.DataFrame:
        if isinstance(df, pd.DataFrame):
            return df
        raise TypeError("fetcher must return pandas DataFrames inside build_returns")

    def build_quote_mid_prices(symbol: str) -> pd.Series:
        df_any = fetcher.fetch_stock_quotes(symbol=symbol, interval=config.horizon, date_=date_, start_time=window_start, end_time=window_end)
        df = _as_pandas_df(df_any)
        if df.empty:
            return _empty(symbol)
        ts = _localize(df["timestamp"])
        bid = cast(pd.Series, df["bid"]).astype(float)
        ask = cast(pd.Series, df["ask"]).astype(float)
        midpoint = (bid + ask) / 2.0
        prices = pd.Series(midpoint.to_numpy(dtype=float), index=ts, name=symbol)
        prices = prices[~prices.index.duplicated(keep="last")]
        return prices.reindex(grid)

    def _build_trade_prices(symbol: str, use_vwap: bool) -> pd.Series:
        df_any = fetcher.fetch_stock_trades(symbol=symbol, date_=date_, start_time=window_start, end_time=window_end)
        df = _as_pandas_df(df_any)
        if df.empty:
            return _empty(symbol)
        ts = _localize(df["timestamp"])
        trades = pd.DataFrame(index=ts)
        trades["price"] = cast(pd.Series, df["price"]).astype(float).to_numpy()
        if use_vwap:
            trades["size"] = cast(pd.Series, df["size"]).astype(float).to_numpy()
        trades = trades.sort_index()
        first_bar_start = grid[0] - horizon_td
        trades_w = trades[(trades.index > first_bar_start) & (trades.index <= grid[-1])].copy()
        if trades_w.empty:
            return _empty(symbol)
        trades_w["bar"] = grid.searchsorted(trades_w.index, side="left")
        out = _empty(symbol)
        if use_vwap:
            trades_w["pv"] = trades_w["price"] * trades_w["size"]
            grouped = trades_w.groupby("bar").agg({"pv": "sum", "size": "sum"})
            values = cast(pd.Series, grouped["pv"] / grouped["size"])
        else:
            values = cast(pd.Series, trades_w.groupby("bar")["price"].last())
        bar_positions = [int(i) for i in values.index.to_list()]
        out.iloc[bar_positions] = values.to_numpy(dtype=float)
        return out

    build_prices: Callable[[str], pd.Series]
    if config.price_source == "quote_mid":
        build_prices = build_quote_mid_prices
    elif config.price_source == "trade_last":
        build_prices = lambda symbol: _build_trade_prices(symbol, use_vwap=False)
    elif config.price_source == "trade_vwap":
        build_prices = lambda symbol: _build_trade_prices(symbol, use_vwap=True)
    else:
        raise NotImplementedError(f"price_source '{config.price_source}' not implemented")

    series_list: list[pd.Series] = []
    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        prices = build_prices(symbol)
        if config.return_type == "log":
            ratio = cast(pd.Series, prices / prices.shift(1))
            ratio_np = ratio.to_numpy(dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                log_returns = np.log(ratio_np)
            invalid = (~np.isfinite(ratio_np)) | (ratio_np <= 0.0) | (~np.isfinite(log_returns))
            log_returns[invalid] = np.nan
            returns = pd.Series(log_returns, index=prices.index, name=symbol)
        elif config.return_type == "simple":
            simple = cast(pd.Series, prices / prices.shift(1) - 1.0)
            simple_np = simple.to_numpy(dtype=float)
            simple_np[~np.isfinite(simple_np)] = np.nan
            returns = pd.Series(simple_np, index=simple.index, name=symbol)
        else:
            raise NotImplementedError(f"return_type '{config.return_type}' not implemented")
        returns.name = symbol
        series_list.append(returns)

    out = pd.concat(series_list, axis=1)
    out = cast(pd.DataFrame, out)
    out.index.name = "timestamp"
    return out.iloc[1:]
