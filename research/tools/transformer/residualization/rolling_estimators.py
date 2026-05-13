from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class RollingExposureEstimator(ABC):
    """Interface for time-varying factor exposure estimators."""

    @abstractmethod
    def estimate_path(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.DataFrame:
        """Estimate a time-indexed beta path for one stock."""


class RollingOLSExposureEstimator(RollingExposureEstimator):
    """Stub for rolling OLS exposure estimation."""

    def __init__(self, window: int, min_obs_per_factor: int = 10, refit_every: int = 1) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        if min_obs_per_factor < 1:
            raise ValueError("min_obs_per_factor must be >= 1")
        if refit_every < 1:
            raise ValueError("refit_every must be >= 1")
        self.window = window
        self.min_obs_per_factor = min_obs_per_factor
        self.refit_every = refit_every

    def estimate_path(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.DataFrame:
        """Return a rolling beta path for one stock."""
        raise NotImplementedError("Rolling OLS estimation has not been implemented yet.")
