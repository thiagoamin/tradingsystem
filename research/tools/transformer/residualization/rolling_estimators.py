from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


class RollingExposureEstimator(ABC):
    """Interface for time-varying factor exposure estimators."""

    @abstractmethod
    def estimate_path(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.DataFrame:
        """Estimate a time-indexed beta path for one stock."""


class RollingOLSExposureEstimator(RollingExposureEstimator):
    """Estimate rolling OLS parameters from trailing, lagged observations.

    At timestamp ``t``, the beta estimate is fit using rows strictly before
    ``t``. An optional ``alpha`` intercept supports daily ETF replications
    without changing the no-intercept default for other workflows.
    """

    def __init__(
        self,
        window: int,
        min_obs_per_factor: int = 10,
        refit_every: int = 1,
        min_obs: int | None = None,
        fit_intercept: bool = False,
    ) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        if min_obs_per_factor < 1:
            raise ValueError("min_obs_per_factor must be >= 1")
        if refit_every < 1:
            raise ValueError("refit_every must be >= 1")
        if min_obs is not None and min_obs < 1:
            raise ValueError("min_obs must be >= 1 when provided")
        if min_obs is not None and min_obs > window:
            raise ValueError("min_obs cannot exceed window")
        self.window = window
        self.min_obs_per_factor = min_obs_per_factor
        self.refit_every = refit_every
        self.min_obs = min_obs
        self.fit_intercept = fit_intercept
        
    def estimate_path(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.DataFrame:
        """Return timestamped parameters estimated from preceding windows.

        Args:
            stock_returns: Returns for one modeled stock.
            factor_returns: Assigned factor returns sharing the same index.

        Returns:
            Parameter DataFrame indexed like ``stock_returns``. Columns hold
            factor betas and, if requested, ``alpha``. Initial rows and failed
            fits contain ``NaN``.

        Raises:
            ValueError: If the stock and factor indices are not identical.
        """
        if not stock_returns.index.equals(factor_returns.index):
            raise ValueError("stock_returns and factor_returns must share the same index")
        factor_names = list(factor_returns.columns)
        if not factor_names:
            raise ValueError("factor_returns must contain at least one factor column")

        output_names = factor_names + (["alpha"] if self.fit_intercept else [])
        betas = pd.DataFrame(np.nan, index=stock_returns.index, columns=output_names, dtype=float)
        last_beta: np.ndarray | None = None
        for position in range(len(stock_returns)):
            if position % self.refit_every != 0 and last_beta is not None:
                betas.iloc[position] = last_beta
                continue
            start = max(0, position - self.window)
            sample = pd.concat(
                [stock_returns.iloc[start:position].rename("_y"), factor_returns.iloc[start:position]],
                axis=1,
            ).dropna()
            required_obs = self.min_obs or self.min_obs_per_factor * len(factor_names)
            if len(sample) < required_obs:
                continue
            x = sample[factor_names].to_numpy(dtype=float)
            y = sample["_y"].to_numpy(dtype=float)
            if np.linalg.matrix_rank(x) < len(factor_names):
                continue
            model = LinearRegression(fit_intercept=self.fit_intercept)
            model.fit(x, y)
            last_beta = np.asarray(model.coef_, dtype=float)
            fitted = (
                np.append(last_beta, float(model.intercept_))
                if self.fit_intercept
                else last_beta
            )
            last_beta = fitted
            betas.iloc[position] = fitted
        return betas
