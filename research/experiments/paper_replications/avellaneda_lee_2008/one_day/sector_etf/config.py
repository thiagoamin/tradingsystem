from __future__ import annotations

"""Fixed modern universe for the paper-style assigned-sector-ETF experiment."""

from dataclasses import asdict
from datetime import date

import pandas as pd

from ..configured_splits import RAW_CLOSE_SPLIT_EVENTS

# The source paper uses a broad, point-in-time universe and one industry ETF
# assigned to each stock. This smaller fixed universe tests the same mechanism
# in modern data, but is not survivorship-free.
SECTOR_STOCKS: dict[str, tuple[str, ...]] = {
    "XLK": ("AAPL", "MSFT", "NVDA", "AVGO", "AMD"),
    "XLF": ("JPM", "BAC", "GS", "MS", "C"),
    "XLE": ("XOM", "CVX", "COP", "SLB", "EOG"),
    "XLV": ("LLY", "JNJ", "MRK", "ABBV", "UNH"),
    "XLI": ("CAT", "HON", "UNP", "UPS", "LMT"),
}
MARKET_FACTOR = "SPY"
STOCK_TO_ETF = {stock: etf for etf, stocks in SECTOR_STOCKS.items() for stock in stocks}
STOCKS = list(STOCK_TO_ETF)
FACTOR_ETFS = list(SECTOR_STOCKS) + [MARKET_FACTOR]
SYMBOLS = STOCKS + FACTOR_ETFS
CONFIGURED_SPLITS = tuple(event for event in RAW_CLOSE_SPLIT_EVENTS if event.symbol in SYMBOLS)

START_DATE = date(2020, 1, 2)
END_DATE = date(2025, 12, 31)
TRADING_START_DATE = date(2020, 7, 1)


def universe_frame() -> pd.DataFrame:
    """Return the fixed stock-to-sector-ETF assignment table."""
    return pd.DataFrame(
        [{"symbol": stock, "sector_etf": etf} for stock, etf in STOCK_TO_ETF.items()]
    )


def configured_split_frame() -> pd.DataFrame:
    """Return the explicitly configured split-adjustment audit table."""
    return pd.DataFrame([asdict(event) for event in CONFIGURED_SPLITS])
