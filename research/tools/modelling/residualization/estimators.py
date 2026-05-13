from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class ExposureEstimator(ABC):
    """Strategy interface for estimating per-stock factor exposures."""

    @abstractmethod
    def estimate(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.Series:
        """Estimate factor betas for one stock from aligned stock and factor returns."""


class OLSExposureEstimator(ExposureEstimator):
    """Ordinary least squares estimator without an intercept."""

    def __init__(self, min_obs_per_factor: int = 10) -> None:
        """Initialize the estimator with a minimum-observation requirement."""
        if min_obs_per_factor < 1:
            raise ValueError("min_obs_per_factor must be >= 1")
        self.min_obs_per_factor = min_obs_per_factor

    def estimate(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.Series:
        """Estimate betas or return NaNs when data are insufficient or rank-deficient."""
        if not stock_returns.index.equals(factor_returns.index):
            raise ValueError("stock_returns and factor_returns must share the same index")
        factor_names = list(factor_returns.columns)
        n_factors = len(factor_names)
        nan_result = pd.Series([np.nan] * n_factors, index=factor_names, dtype=float)
        combined = pd.concat([stock_returns.rename("_y"), factor_returns], axis=1).dropna()
        if len(combined) < self.min_obs_per_factor * n_factors:
            return nan_result
        y = combined["_y"].to_numpy(dtype=float)
        x = combined[factor_names].to_numpy(dtype=float)
        try:
            betas, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
        except np.linalg.LinAlgError:
            return nan_result
        if rank < n_factors:
            return nan_result
        return pd.Series(betas, index=factor_names, dtype=float)
