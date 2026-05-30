from __future__ import annotations

"""Daily close, volume, and return panels derived from ThetaData EOD records."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from research.tools.processing.corporate_actions import StockSplit, apply_stock_split_adjustments

DailyReturnType = Literal["log", "simple"]


@dataclass(frozen=True)
class DailyEodPanels:
    """Daily EOD price/volume panels split into stocks and factor ETFs.

    ``closes`` and ``returns`` use the configured split-adjusted series;
    ``raw_closes`` and ``raw_volumes`` preserve the ThetaData values used as
    input. When volumes are present, ``volumes`` expresses historical share
    volume on the same split-adjusted share basis as ``closes``.
    """

    closes: pd.DataFrame
    returns: pd.DataFrame
    stocks: tuple[str, ...]
    factor_etfs: tuple[str, ...]
    raw_closes: pd.DataFrame
    split_adjustment_factors: pd.DataFrame
    split_adjusted: bool
    dividend_adjusted: bool = False
    raw_volumes: pd.DataFrame | None = None
    volumes: pd.DataFrame | None = None
    dollar_volumes: pd.DataFrame | None = None

    @property
    def stock_returns(self) -> pd.DataFrame:
        """Return daily returns for modeled stocks only."""
        return self.returns.loc[:, list(self.stocks)]

    @property
    def factor_returns(self) -> pd.DataFrame:
        """Return daily returns for factor ETFs only."""
        return self.returns.loc[:, list(self.factor_etfs)]

    @property
    def has_volume(self) -> bool:
        """Return whether the EOD panel includes ThetaData volume fields."""
        return self.volumes is not None

    @property
    def stock_volumes(self) -> pd.DataFrame:
        """Return split-adjusted share volumes for modeled stocks only."""
        return self._require_volume_panel(self.volumes, "volumes").loc[:, list(self.stocks)]

    @property
    def factor_volumes(self) -> pd.DataFrame:
        """Return split-adjusted share volumes for factor ETFs only."""
        return self._require_volume_panel(self.volumes, "volumes").loc[:, list(self.factor_etfs)]

    @property
    def stock_dollar_volumes(self) -> pd.DataFrame:
        """Return close-times-volume dollar volumes for modeled stocks only."""
        return self._require_volume_panel(self.dollar_volumes, "dollar_volumes").loc[:, list(self.stocks)]

    @property
    def corporate_action_adjusted(self) -> bool:
        """Return whether split and dividend adjustments have both been applied."""
        return self.split_adjusted and self.dividend_adjusted

    @staticmethod
    def _require_volume_panel(panel: pd.DataFrame | None, name: str) -> pd.DataFrame:
        if panel is None:
            raise ValueError(f"DailyEodPanels does not include {name}; rebuild from EOD records with volume.")
        return panel


def build_daily_eod_panels(
    records: pd.DataFrame,
    stocks: list[str],
    factor_etfs: list[str],
    return_type: DailyReturnType = "log",
    split_events: Sequence[StockSplit] = (),
) -> DailyEodPanels:
    """Build daily split-adjusted close, volume, and return panels from EOD responses.

    Args:
        records: Long EOD records containing ``symbol``, ``created``, and
            ``close`` columns. If ``volume`` is present it is preserved and
            split-adjusted onto the same share basis as ``closes``.
        stocks: Modeled stock symbols.
        factor_etfs: ETF symbols supplying factor returns.
        return_type: ``"log"`` or ``"simple"`` daily close return.
        split_events: Verified forward splits still visible as discontinuities
            in the raw ThetaData close records.

    Returns:
        Raw closes, optional raw volumes, split-adjusted closes/volumes, and
        return panels ordered as stocks followed by factor ETFs.

    Raises:
        ValueError: If inputs or required EOD columns are invalid.

    Notes:
        The split schedule is explicit because the ThetaData EOD endpoint does
        not expose a corporate-action feed here. Dividends are not adjusted.
    """
    required = {"symbol", "created", "close"}
    missing = sorted(required - set(records.columns))
    if missing:
        raise ValueError(f"EOD records are missing required columns: {missing}")
    if return_type not in {"log", "simple"}:
        raise ValueError("return_type must be either 'log' or 'simple'")

    stock_symbols = _normalize_symbols(stocks, label="stocks")
    factor_symbols = _normalize_symbols(factor_etfs, label="factor_etfs")
    symbols = stock_symbols + factor_symbols
    if len(set(symbols)) != len(symbols):
        raise ValueError("stocks and factor_etfs must not overlap")

    columns = ["symbol", "created", "close"]
    has_volume = "volume" in records.columns
    if has_volume:
        columns.append("volume")
    normalized = records.loc[:, columns].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper()
    normalized["date"] = pd.to_datetime(normalized["created"]).dt.date
    normalized["close"] = pd.to_numeric(normalized["close"], errors="coerce")
    if has_volume:
        normalized["volume"] = pd.to_numeric(normalized["volume"], errors="coerce")
    normalized = normalized[normalized["symbol"].isin(symbols)]
    if normalized["close"].le(0).any():
        raise ValueError("ThetaData EOD close values must be positive")
    if has_volume and normalized["volume"].lt(0).any():
        raise ValueError("ThetaData EOD volume values must be non-negative")

    deduped = normalized.drop_duplicates(subset=["date", "symbol"], keep="last")
    raw_closes = _pivot_panel(deduped, symbols, value="close")
    raw_closes.index = pd.DatetimeIndex(raw_closes.index, name="date")
    if raw_closes.empty:
        raise ValueError("No EOD records matched requested stocks or factor_etfs")

    closes, adjustment_factors = apply_stock_split_adjustments(raw_closes, split_events)
    raw_volumes: pd.DataFrame | None = None
    volumes: pd.DataFrame | None = None
    dollar_volumes: pd.DataFrame | None = None
    if has_volume:
        raw_volumes = _pivot_panel(deduped, symbols, value="volume")
        raw_volumes.index = pd.DatetimeIndex(raw_volumes.index, name="date")
        volumes = raw_volumes / adjustment_factors
        volumes.index.name = "date"
        dollar_volumes = closes * volumes
        dollar_volumes.index.name = "date"

    if return_type == "log":
        returns = np.log(closes / closes.shift(1))
    else:
        returns = closes.pct_change(fill_method=None)
    returns.index.name = "date"
    return DailyEodPanels(
        closes=closes,
        returns=returns,
        stocks=tuple(stock_symbols),
        factor_etfs=tuple(factor_symbols),
        raw_closes=raw_closes,
        split_adjustment_factors=adjustment_factors,
        split_adjusted=bool(split_events),
        raw_volumes=raw_volumes,
        volumes=volumes,
        dollar_volumes=dollar_volumes,
    )


def _normalize_symbols(symbols: list[str], label: str) -> list[str]:
    normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


def _pivot_panel(records: pd.DataFrame, symbols: list[str], value: str) -> pd.DataFrame:
    return (
        records.pivot(index="date", columns="symbol", values=value)
        .reindex(columns=symbols)
        .sort_index()
    )
