from __future__ import annotations

"""Corporate-action transformations for research price panels."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class StockSplit:
    """A forward stock split that must be removed from a raw close series.

    Args:
        symbol: Security ticker affected by the split.
        effective_date: First trading date with the post-split share price.
        ratio: New shares received for each old share, such as ``4.0`` for a
            four-for-one forward split.
        source: Optional audit reference for the configured action.
    """

    symbol: str
    effective_date: date
    ratio: float
    source: str = ""

    def __post_init__(self) -> None:
        normalized = self.symbol.strip().upper()
        if not normalized:
            raise ValueError("split symbol must be non-empty")
        if self.ratio <= 0:
            raise ValueError("split ratio must be positive")
        object.__setattr__(self, "symbol", normalized)


def build_split_adjustment_factors(
    closes: pd.DataFrame, split_events: Sequence[StockSplit]
) -> pd.DataFrame:
    """Return multiplicative factors that express historical closes on the latest share basis.

    Raw closes before a forward split are divided by the split ratio. For
    multiple events in one symbol, prior prices receive each applicable factor.

    Raises:
        ValueError: If a split symbol is absent from the close panel.
    """
    factors = pd.DataFrame(1.0, index=closes.index, columns=closes.columns)
    for event in split_events:
        if event.symbol not in closes.columns:
            raise ValueError(f"split symbol '{event.symbol}' is absent from close panel")
        before_split = factors.index < pd.Timestamp(event.effective_date)
        factors.loc[before_split, event.symbol] /= event.ratio
    return factors


def apply_stock_split_adjustments(
    closes: pd.DataFrame, split_events: Sequence[StockSplit]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return split-adjusted closes and the factor panel used to compute them."""
    factors = build_split_adjustment_factors(closes, split_events)
    return closes * factors, factors
