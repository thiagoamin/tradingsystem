from __future__ import annotations

"""Verified splits visible as discontinuities in the ThetaData raw EOD panel."""

from dataclasses import asdict
from datetime import date

import pandas as pd

from research.tools.processing import StockSplit

# This schedule corrects raw ThetaData close discontinuities observed in this
# experiment range. It is intentionally explicit and audit-friendly.
RAW_CLOSE_SPLIT_EVENTS = (
    StockSplit(
        "AAPL",
        date(2020, 8, 31),
        4.0,
        "https://www.apple.com/newsroom/2020/07/apple-reports-third-quarter-results/",
    ),
    StockSplit(
        "NVDA",
        date(2021, 7, 20),
        4.0,
        "https://nvidianews.nvidia.com/news/nvidia-announces-four-for-one-stock-split-pending-stockholder-approval-at-annual-meeting-set-for-june-3",
    ),
    StockSplit(
        "NVDA",
        date(2024, 6, 10),
        10.0,
        "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2025",
    ),
    StockSplit(
        "AVGO",
        date(2024, 7, 15),
        10.0,
        "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2024-financial",
    ),
    StockSplit(
        "XLK",
        date(2025, 12, 5),
        2.0,
        "https://www.ssga.com/us/en/intermediary/library-content/products/fund-docs/etfs/us/information-schedules/select-sector-spdr-fund-share-splits-faq.pdf",
    ),
    StockSplit(
        "XLE",
        date(2025, 12, 5),
        2.0,
        "https://www.ssga.com/us/en/intermediary/library-content/products/fund-docs/etfs/us/information-schedules/select-sector-spdr-fund-share-splits-faq.pdf",
    ),
)


def split_event_audit_frame() -> pd.DataFrame:
    """Return the configured split schedule as an auditable table."""
    return pd.DataFrame([asdict(event) for event in RAW_CLOSE_SPLIT_EVENTS])
