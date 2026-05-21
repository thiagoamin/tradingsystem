from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.processing.quote_variables import build_quote_variables
from research.tools.processing.returns_config import ReturnsConfig

TradeVariable = Literal[
    "trade_count",
    "trade_volume",
    "dollar_volume",
    "vwap",
    "signed_volume_imbalance",
    "vwap_gap",
]
TradeVariablePanels = dict[str, pd.DataFrame]

DEFAULT_TRADE_VARIABLES: tuple[TradeVariable, ...] = (
    "trade_count",
    "trade_volume",
    "dollar_volume",
    "vwap",
    "signed_volume_imbalance",
    "vwap_gap",
)


def build_trade_variables(
    config: ReturnsConfig,
    fetcher: ThetaDataFetcher,
    symbols: list[str],
    date_: date,
    start_time: time | None = None,
    end_time: time | None = None,
    variables: Sequence[TradeVariable] = DEFAULT_TRADE_VARIABLES,
    quote_mid: pd.DataFrame | None = None,
) -> TradeVariablePanels:
    """Build horizon-aligned trade variables from ThetaData trade+quote records.

    Implemented variables from ``variables.pdf`` are trade count, share volume,
    dollar volume, VWAP, signed volume imbalance, and VWAP gap. Trades are signed
    using the NBBO midpoint paired to each trade by ThetaData.
    """
    if not symbols:
        raise ValueError("symbols must be non-empty")
    if getattr(fetcher, "dataframe_type", None) != "pandas":
        raise ValueError("fetcher must be configured with dataframe_type='pandas'")
    if config.horizon.endswith("d"):
        raise NotImplementedError("daily horizons not supported for intraday trade variables")
    requested = _validate_variables(variables)
    window_start = start_time if start_time is not None else config.session_start
    window_end = end_time if end_time is not None else config.session_end
    if window_start >= window_end:
        raise ValueError("start_time must be strictly before end_time")

    grid = _build_grid(config=config, date_=date_, window_start=window_start, window_end=window_end)
    normalized_symbols = [symbol.upper() for symbol in symbols]
    if "vwap_gap" in requested and quote_mid is None:
        quote_mid = build_quote_variables(
            config=config,
            fetcher=fetcher,
            symbols=normalized_symbols,
            date_=date_,
            start_time=start_time,
            end_time=end_time,
            variables=("mid",),
        )["mid"]

    symbol_values = {name: [] for name in requested}
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
            quote_mid=quote_mid[symbol] if quote_mid is not None and symbol in quote_mid.columns else None,
        )
        for name in requested:
            symbol_values[name].append(values[name])

    return {
        name: pd.concat(series_list, axis=1).reindex(columns=normalized_symbols)
        for name, series_list in symbol_values.items()
    }


def _validate_variables(variables: Sequence[TradeVariable]) -> tuple[TradeVariable, ...]:
    valid = set(DEFAULT_TRADE_VARIABLES)
    unknown = sorted(set(variables) - valid)
    if unknown:
        raise ValueError(f"Unsupported trade variables: {unknown}. Supported values: {sorted(valid)}")
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
    requested: tuple[TradeVariable, ...],
    quote_mid: pd.Series | None,
) -> dict[TradeVariable, pd.Series]:
    df_any = fetcher.fetch_stock_trade_quotes(
        symbol=symbol,
        date_=date_,
        start_time=start_time,
        end_time=end_time,
    )
    df = _as_pandas_df(df_any)
    empty = _empty_outputs(grid=grid, symbol=symbol)
    if df.empty:
        return {name: empty[name] for name in requested}

    timestamp_col = "trade_timestamp" if "trade_timestamp" in df.columns else "timestamp"
    ts = _localize(cast(pd.Series, df[timestamp_col]), ZoneInfo(config.tz))
    trades = pd.DataFrame(index=ts)
    trades["price"] = cast(pd.Series, df["price"]).astype(float).to_numpy()
    trades["size"] = cast(pd.Series, df["size"]).astype(float).to_numpy()
    bid = cast(pd.Series, df["bid"]).astype(float).to_numpy()
    ask = cast(pd.Series, df["ask"]).astype(float).to_numpy()
    trades["trade_mid"] = (bid + ask) / 2.0
    trades["signed_size"] = np.where(trades["price"] >= trades["trade_mid"], trades["size"], -trades["size"])
    trades = trades.sort_index()

    first_bar_start = grid[0] - config.horizon_timedelta()
    in_window = (trades.index > first_bar_start) & (trades.index <= grid[-1])
    trades = trades[in_window].copy()
    if trades.empty:
        return {name: empty[name] for name in requested}

    bar_positions = grid.searchsorted(trades.index, side="left")
    trades = trades[bar_positions < len(grid)].copy()
    trades["bar"] = bar_positions[bar_positions < len(grid)]
    trades["dollar_value"] = trades["price"] * trades["size"]
    grouped = trades.groupby("bar").agg(
        trade_count=("price", "size"),
        trade_volume=("size", "sum"),
        dollar_volume=("dollar_value", "sum"),
        signed_volume=("signed_size", "sum"),
    )

    out = _empty_outputs(grid=grid, symbol=symbol)
    for name in ("trade_count", "trade_volume", "dollar_volume"):
        out[name].iloc[grouped.index.to_numpy(dtype=int)] = grouped[name].to_numpy(dtype=float)

    vwap = _safe_divide(grouped["dollar_volume"].to_numpy(dtype=float), grouped["trade_volume"].to_numpy(dtype=float))
    svi = _safe_divide(grouped["signed_volume"].to_numpy(dtype=float), grouped["trade_volume"].to_numpy(dtype=float))
    bar_index = grouped.index.to_numpy(dtype=int)
    out["vwap"].iloc[bar_index] = vwap
    out["signed_volume_imbalance"].iloc[bar_index] = svi
    if quote_mid is not None:
        aligned_mid = quote_mid.reindex(grid).to_numpy(dtype=float)[bar_index]
        out["vwap_gap"].iloc[bar_index] = _safe_divide(vwap - aligned_mid, aligned_mid)
    return {name: out[name] for name in requested}


def _empty_outputs(grid: pd.DatetimeIndex, symbol: str) -> dict[TradeVariable, pd.Series]:
    zeros = ("trade_count", "trade_volume", "dollar_volume")
    return {
        name: pd.Series(0.0 if name in zeros else np.nan, index=grid, name=symbol, dtype=float)
        for name in DEFAULT_TRADE_VARIABLES
    }


def _as_pandas_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df
    raise TypeError("fetcher must return pandas DataFrames inside build_trade_variables")


def _localize(ts_raw: pd.Series, tz: ZoneInfo) -> pd.DatetimeIndex:
    ts_index = pd.DatetimeIndex(pd.to_datetime(ts_raw))
    if ts_index.tz is None:
        return ts_index.tz_localize(tz)
    return ts_index.tz_convert(tz)


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    numerator_np = np.asarray(numerator, dtype=float)
    denominator_np = np.asarray(denominator, dtype=float)
    out = np.full_like(numerator_np, np.nan, dtype=float)
    np.divide(numerator_np, denominator_np, out=out, where=denominator_np != 0.0)
    out[~np.isfinite(out)] = np.nan
    return out
