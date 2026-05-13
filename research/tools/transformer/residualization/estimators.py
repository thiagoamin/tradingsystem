from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler


class ExposureEstimator(ABC):
    """Strategy interface for estimating per-stock factor exposures."""

    @abstractmethod
    def estimate(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.Series:
        """Estimate factor betas for one stock from aligned stock and factor returns."""


class _LinearExposureEstimator(ExposureEstimator):
    """Shared preprocessing and validation for linear exposure estimators."""

    def __init__(self, min_obs_per_factor: int = 10) -> None:
        if min_obs_per_factor < 1:
            raise ValueError("min_obs_per_factor must be >= 1")
        self.min_obs_per_factor = min_obs_per_factor

    def estimate(self, stock_returns: pd.Series, factor_returns: pd.DataFrame) -> pd.Series:
        """Estimate betas or return NaNs when data are insufficient or invalid."""
        if not stock_returns.index.equals(factor_returns.index):
            raise ValueError("stock_returns and factor_returns must share the same index")
        factor_names = list(factor_returns.columns)
        nan_result = pd.Series(np.nan, index=factor_names, dtype=float)
        combined = pd.concat([stock_returns.rename("_y"), factor_returns], axis=1).dropna()
        if len(combined) < self.min_obs_per_factor * len(factor_names):
            return nan_result
        y = combined["_y"].to_numpy(dtype=float)
        x = combined[factor_names].to_numpy(dtype=float)
        if x.ndim != 2 or x.shape[1] == 0:
            return nan_result
        try:
            betas = self._solve(x, y)
        except np.linalg.LinAlgError:
            return nan_result
        if betas is None or betas.shape != (len(factor_names),):
            return nan_result
        return pd.Series(betas, index=factor_names, dtype=float)

    @abstractmethod
    def _solve(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """Solve for betas given a clean design matrix and target vector."""

    def _scale_inputs(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float] | None:
        """Return scaled inputs plus the original scale factors used to recover betas."""
        x_scaler = StandardScaler(with_mean=False)
        y_scaler = StandardScaler(with_mean=False)
        x_scaled = x_scaler.fit_transform(x)
        y_scaled = y_scaler.fit_transform(y.reshape(-1, 1)).ravel()
        x_scale = np.asarray(x_scaler.scale_, dtype=float)
        y_scale = float(np.asarray(y_scaler.scale_, dtype=float)[0])
        if np.any(x_scale == 0.0) or y_scale == 0.0:
            return None
        return x_scaled, y_scaled, x_scale, y_scale

    def _unscale_betas(self, beta_scaled: np.ndarray, x_scale: np.ndarray, y_scale: float) -> np.ndarray:
        """Map coefficients from standardized units back to the original return units."""
        return np.asarray(beta_scaled, dtype=float) * (y_scale / x_scale)


class OLSExposureEstimator(_LinearExposureEstimator):
    """Ordinary least squares estimator without an intercept."""

    def _solve(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """Fit no-intercept OLS via scikit-learn and reject rank-deficient fits."""
        rank = int(np.linalg.matrix_rank(x))
        if rank < x.shape[1]:
            return None
        model = LinearRegression(fit_intercept=False)
        model.fit(x, y)
        return np.asarray(model.coef_, dtype=float)


class RidgeExposureEstimator(_LinearExposureEstimator):
    """Ridge estimator without an intercept for more stable collinear-factor fits."""

    def __init__(self, alpha: float = 1.0, min_obs_per_factor: int = 10) -> None:
        super().__init__(min_obs_per_factor=min_obs_per_factor)
        if alpha < 0:
            raise ValueError("alpha must be >= 0")
        self.alpha = float(alpha)

    def _solve(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """Fit no-intercept ridge on standardized data, then map betas back to original units."""
        scaled = self._scale_inputs(x, y)
        if scaled is None:
            return None
        x_scaled, y_scaled, x_scale, y_scale = scaled
        model = Ridge(alpha=self.alpha, fit_intercept=False)
        model.fit(x_scaled, y_scaled)
        return self._unscale_betas(model.coef_, x_scale, y_scale)


class ElasticNetExposureEstimator(_LinearExposureEstimator):
    """Elastic net estimator without an intercept for sparse but stable factor fits."""

    def __init__(self, alpha: float = 1.0, l1_ratio: float = 0.5, min_obs_per_factor: int = 10) -> None:
        super().__init__(min_obs_per_factor=min_obs_per_factor)
        if alpha < 0:
            raise ValueError("alpha must be >= 0")
        if not 0 <= l1_ratio <= 1:
            raise ValueError("l1_ratio must be between 0 and 1")
        self.alpha = float(alpha)
        self.l1_ratio = float(l1_ratio)

    def _solve(self, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        """Fit no-intercept elastic net on standardized data, then map betas back to original units."""
        scaled = self._scale_inputs(x, y)
        if scaled is None:
            return None
        x_scaled, y_scaled, x_scale, y_scale = scaled
        model = ElasticNet(alpha=self.alpha, l1_ratio=self.l1_ratio, fit_intercept=False, max_iter=10000)
        model.fit(x_scaled, y_scaled)
        return self._unscale_betas(model.coef_, x_scale, y_scale)
