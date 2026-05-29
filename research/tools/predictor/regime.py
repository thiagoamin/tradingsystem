from __future__ import annotations

"""Residual regime predictors for trend-vs-mean-reversion decisions."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from research.tools.predictor.base import PanelPredictor


class ResidualRegimePredictor(PanelPredictor):
    """Predict whether residual trend or residual mean reversion is favored.

    The predictor fits one sklearn classifier per symbol. By default it uses a
    standardized logistic regression with balanced class weights. `predict`
    returns the estimated probability that the trend-following residual rule is
    preferable to the mean-reversion residual rule.
    """

    def __init__(
        self,
        estimator: Any | None = None,
        min_obs: int = 60,
        trend_threshold: float = 0.55,
        mean_reversion_threshold: float = 0.45,
    ) -> None:
        """Initialize classifier template and probability thresholds.

        Args:
            estimator: sklearn-compatible classifier implementing `fit` and
                `predict_proba`. Defaults to scaled logistic regression.
            min_obs: Minimum complete observations needed per symbol.
            trend_threshold: Probability at or above this value classifies as trend.
            mean_reversion_threshold: Probability at or below this value classifies as mean reversion.

        Raises:
            ValueError: If thresholds or minimum observations are invalid.
        """
        if min_obs < 1:
            raise ValueError("min_obs must be >= 1")
        if not 0.0 < mean_reversion_threshold < trend_threshold < 1.0:
            raise ValueError("thresholds must satisfy 0 < mean_reversion_threshold < trend_threshold < 1")
        self.estimator = estimator or make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1_000, class_weight="balanced")
        )
        self.min_obs = int(min_obs)
        self.trend_threshold = float(trend_threshold)
        self.mean_reversion_threshold = float(mean_reversion_threshold)
        self._models: dict[str, Any] = {}
        self._feature_names: dict[str, list[str]] = {}

    @property
    def fitted_symbols(self) -> list[str]:
        """Return symbols with fitted regime classifiers."""
        return list(self._models)

    def fit(self, features: pd.DataFrame, target: pd.DataFrame | pd.Series) -> ResidualRegimePredictor:
        """Fit one classifier per symbol.

        Args:
            features: MultiIndex-column feature panel with `(symbol, feature)` columns.
            target: Wide panel of binary labels where `1` means trend was better and `0` means mean reversion was better.

        Returns:
            Self, with fitted sklearn models stored by symbol.

        Raises:
            ValueError: If feature columns are not a MultiIndex.
        """
        self._validate_features(features)
        target_df = target.to_frame() if isinstance(target, pd.Series) else target
        self._models = {}
        self._feature_names = {}
        for symbol in target_df.columns.astype(str):
            if symbol not in features.columns.get_level_values(0):
                continue
            x_raw = self._symbol_features(features, symbol)
            y_raw = target_df[symbol].rename("_target")
            combined = pd.concat([y_raw, x_raw], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
            if len(combined) < self.min_obs or combined["_target"].nunique() < 2:
                continue
            y = combined["_target"].astype(int).to_numpy()
            x_df = combined.drop(columns="_target")
            model = clone(self.estimator)
            model.fit(x_df.to_numpy(dtype=float), y)
            if not hasattr(model, "predict_proba"):
                raise TypeError("estimator must implement predict_proba after fitting")
            self._models[symbol] = model
            self._feature_names[symbol] = list(x_df.columns.astype(str))
        return self

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return trend-regime probabilities for each fitted symbol."""
        return self.predict_proba(features)

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return `P(trend regime)` for each fitted symbol and timestamp.

        Raises:
            RuntimeError: If no symbol classifier has been fitted.
            ValueError: If feature columns are not a MultiIndex.
        """
        if not self._models:
            raise RuntimeError("predictor has not been fitted yet")
        self._validate_features(features)
        output = pd.DataFrame(np.nan, index=features.index, columns=self.fitted_symbols, dtype=float)
        for symbol, model in self._models.items():
            x_df = self._symbol_features(features, symbol).reindex(columns=self._feature_names[symbol])
            valid = x_df.replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
            if not valid.any():
                continue
            proba = model.predict_proba(x_df.loc[valid].to_numpy(dtype=float))
            class_index = list(model.classes_).index(1)
            output.loc[valid, symbol] = proba[:, class_index]
        return output

    def classify(self, features: pd.DataFrame) -> pd.DataFrame:
        """Convert regime probabilities into trend, mean-reversion, or neutral labels.

        Returns:
            DataFrame with `1.0` for trend, `-1.0` for mean reversion, and `0.0` for uncertain rows.
        """
        probabilities = self.predict_proba(features)
        regimes = pd.DataFrame(0.0, index=probabilities.index, columns=probabilities.columns)
        regimes[probabilities >= self.trend_threshold] = 1.0
        regimes[probabilities <= self.mean_reversion_threshold] = -1.0
        regimes[probabilities.isna()] = np.nan
        return regimes

    @staticmethod
    def _symbol_features(features: pd.DataFrame, symbol: str) -> pd.DataFrame:
        return features.xs(symbol, axis=1, level=0, drop_level=True).copy()

    @staticmethod
    def _validate_features(features: pd.DataFrame) -> None:
        if features.empty:
            raise ValueError("features must be non-empty")
        if not isinstance(features.columns, pd.MultiIndex):
            raise ValueError("features columns must be a MultiIndex of (symbol, feature)")


def build_residual_regime_target(
    residual_returns: pd.DataFrame,
    trend_score: pd.DataFrame,
    displacement_score: pd.DataFrame,
    min_abs_score: float = 0.25,
    pnl_margin: float = 0.0,
) -> pd.DataFrame:
    """Build binary labels for trend-vs-mean-reversion residual regimes.

    For each symbol/date, trend direction is `sign(trend_score)` and mean-reversion
    direction is `-sign(displacement_score)`. The label is `1` when the trend
    direction would have earned more next residual return, `0` when the
    mean-reversion direction would have earned more, and `NaN` when the choice is
    not distinct or the payoff difference is too small.

    Args:
        residual_returns: Realized residual returns for the decision period.
        trend_score: Causal trend scores known before `residual_returns` is realized.
        displacement_score: Causal displacement scores known before `residual_returns` is realized.
        min_abs_score: Ignore weak trend/displacement scores below this absolute value.
        pnl_margin: Minimum payoff advantage required to assign a label.

    Returns:
        Wide binary label panel aligned to `residual_returns`.

    Raises:
        ValueError: If score thresholds are invalid or panel shapes cannot align.
    """
    if min_abs_score < 0:
        raise ValueError("min_abs_score must be non-negative")
    if pnl_margin < 0:
        raise ValueError("pnl_margin must be non-negative")
    trend_score = _align_like(trend_score, residual_returns, "trend_score")
    displacement_score = _align_like(displacement_score, residual_returns, "displacement_score")
    realized = residual_returns.astype(float)

    trend_direction = np.sign(trend_score).where(trend_score.abs() >= min_abs_score)
    mr_direction = (-np.sign(displacement_score)).where(displacement_score.abs() >= min_abs_score)
    distinct = trend_direction.notna() & mr_direction.notna() & trend_direction.ne(mr_direction)
    trend_payoff = trend_direction * realized
    mr_payoff = mr_direction * realized

    target = pd.DataFrame(np.nan, index=realized.index, columns=realized.columns, dtype=float)
    target[distinct & (trend_payoff > mr_payoff + pnl_margin)] = 1.0
    target[distinct & (mr_payoff > trend_payoff + pnl_margin)] = 0.0
    return target


def _align_like(panel: pd.DataFrame, reference: pd.DataFrame, name: str) -> pd.DataFrame:
    missing = sorted(set(reference.columns) - set(panel.columns))
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")
    return panel.reindex(index=reference.index, columns=reference.columns).astype(float)
