from __future__ import annotations

import numpy as np
import pandas as pd

from research.tools.predictor.base import PanelPredictor


class RecursiveLeastSquaresResidualPredictor(PanelPredictor):
    """State-space style linear predictor with recursive least squares updates.

    The coefficient vector for each stock is treated as a slowly changing state.
    ``forgetting_factor`` controls how quickly old observations lose influence.
    Predictions are next-bar residual forecasts using fixed coefficients learned
    during ``fit``; ``predict`` does not update the state, so test predictions stay
    out of sample.
    """

    def __init__(self, forgetting_factor: float = 0.98, ridge: float = 1e-3, min_obs: int = 30) -> None:
        if not 0.0 < forgetting_factor <= 1.0:
            raise ValueError("forgetting_factor must be in (0, 1]")
        if ridge <= 0:
            raise ValueError("ridge must be > 0")
        if min_obs < 1:
            raise ValueError("min_obs must be >= 1")
        self.forgetting_factor = float(forgetting_factor)
        self.ridge = float(ridge)
        self.min_obs = int(min_obs)
        self._betas: dict[str, pd.Series] = {}

    @property
    def coefficients(self) -> pd.DataFrame:
        """Return fitted coefficients indexed by symbol."""
        if not self._betas:
            raise RuntimeError("predictor has not been fitted yet")
        return pd.DataFrame(self._betas).T

    def fit(self, features: pd.DataFrame, target: pd.DataFrame | pd.Series) -> RecursiveLeastSquaresResidualPredictor:
        """Estimate one recursive linear model per target symbol."""
        target_df = target.to_frame() if isinstance(target, pd.Series) else target
        if not isinstance(features.columns, pd.MultiIndex):
            raise ValueError("features columns must be a MultiIndex of (symbol, feature)")
        self._betas = {}
        for symbol in target_df.columns:
            if symbol not in features.columns.get_level_values(0):
                continue
            x_raw = features[symbol].copy()
            y_raw = target_df[symbol].rename("_target")
            combined = pd.concat([y_raw, x_raw], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
            if len(combined) < self.min_obs:
                continue
            y = combined["_target"].to_numpy(dtype=float)
            x = combined.drop(columns=["_target"]).to_numpy(dtype=float)
            feature_names = list(combined.drop(columns=["_target"]).columns)
            beta = self._fit_one(x=x, y=y)
            self._betas[symbol] = pd.Series(beta, index=["intercept", *feature_names], dtype=float)
        return self

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Generate next-bar residual forecasts for each fitted symbol."""
        if not self._betas:
            raise RuntimeError("predictor has not been fitted yet")
        if not isinstance(features.columns, pd.MultiIndex):
            raise ValueError("features columns must be a MultiIndex of (symbol, feature)")
        predictions: dict[str, pd.Series] = {}
        for symbol, beta in self._betas.items():
            if symbol not in features.columns.get_level_values(0):
                continue
            x_df = features[symbol].reindex(columns=list(beta.index[1:]))
            x = x_df.to_numpy(dtype=float)
            x_aug = np.column_stack([np.ones(len(x)), x])
            pred = x_aug @ beta.to_numpy(dtype=float)
            pred[~np.isfinite(pred)] = np.nan
            predictions[symbol] = pd.Series(pred, index=features.index, name=symbol)
        return pd.DataFrame(predictions, index=features.index)

    def _fit_one(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        x_aug = np.column_stack([np.ones(len(x)), x])
        n_features = x_aug.shape[1]
        beta = np.zeros(n_features, dtype=float)
        covariance = np.eye(n_features, dtype=float) / self.ridge
        lam = self.forgetting_factor
        for row, value in zip(x_aug, y, strict=True):
            row_2d = row.reshape(-1, 1)
            denom = lam + float((row_2d.T @ covariance @ row_2d)[0, 0])
            gain = (covariance @ row_2d / denom).ravel()
            error = value - float(row @ beta)
            beta = beta + gain * error
            covariance = (covariance - np.outer(gain, row) @ covariance) / lam
        return beta
