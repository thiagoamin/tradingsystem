from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """Base interface for converting transformed data or forecasts into trading decisions."""

    @abstractmethod
    def generate(self, data: pd.DataFrame) -> pd.DataFrame | pd.Series:
        """Generate strategy outputs such as scores, signals, or positions."""


PanelStrategy = Strategy

__all__ = ["PanelStrategy", "Strategy"]
