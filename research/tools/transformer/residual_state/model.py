from __future__ import annotations

"""Causal residual state features for hybrid mean-reversion/trend strategies."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from research.tools.transformer.mean_reversion.ou_estimator import OUEstimator


@dataclass(frozen=True)
class ResidualStateResult:
    """Residual state panels aligned to a residual-return input panel.

    Attributes:
        features: MultiIndex-column panel with columns ``(symbol, feature)``.
        residual_level: Trailing cumulative residual return ending at ``t-1``.
        displacement_score: Z-score of the trailing cumulative residual path.
        trend_score: Endpoint residual trend normalized by residual volatility.
        trend_slope: Linear-regression slope of the trailing residual level.
        trend_r2: Linear-regression fit quality for the trailing residual level.
        residual_volatility: Trailing residual-return volatility ending at ``t-1``.
        relative_volume: Prior-day volume divided by trailing average volume, if supplied.
        dollar_volume_zscore: Prior-day dollar-volume z-score, if supplied.
    """

    features: pd.DataFrame
    residual_level: pd.DataFrame
    displacement_score: pd.DataFrame
    trend_score: pd.DataFrame
    trend_slope: pd.DataFrame
    trend_r2: pd.DataFrame
    residual_volatility: pd.DataFrame
    relative_volume: pd.DataFrame | None = None
    dollar_volume_zscore: pd.DataFrame | None = None
    ou_s_score: pd.DataFrame | None = None
    ou_mean_reversion_days: pd.DataFrame | None = None


class ResidualStateTransformer:
    """Build no-lookahead residual state features from daily residual returns.

    At timestamp ``t``, every output uses information available through
    ``t-1`` only. This makes the state panel suitable for a daily backtest
    engine that applies signals dated ``t`` to return row ``t``.
    """

    def __init__(
        self,
        level_window: int = 60,
        trend_window: int = 20,
        volatility_window: int = 20,
        volume_window: int = 60,
        ou_estimator: OUEstimator | None = None,
    ) -> None:
        """Configure trailing windows for residual and volume state features.

        Args:
            level_window: Length used for cumulative residual displacement.
            trend_window: Length used for residual trend regression.
            volatility_window: Length used for residual-return volatility.
            volume_window: Length used for relative-volume normalization.

        Raises:
            ValueError: If any window is smaller than two observations.
        """
        self.level_window = self._validate_window(level_window, "level_window")
        self.trend_window = self._validate_window(trend_window, "trend_window")
        self.volatility_window = self._validate_window(volatility_window, "volatility_window")
        self.volume_window = self._validate_window(volume_window, "volume_window")
        self.ou_estimator = ou_estimator

    def transform(
        self,
        residual_returns: pd.DataFrame,
        volumes: pd.DataFrame | None = None,
        dollar_volumes: pd.DataFrame | None = None,
    ) -> ResidualStateResult:
        """Transform residual returns into causal residual state features.

        Args:
            residual_returns: Wide residual-return panel indexed by date.
            volumes: Optional split-adjusted share-volume panel.
            dollar_volumes: Optional close-times-volume dollar-volume panel.

        Returns:
            ResidualStateResult with individual feature panels and one combined
            MultiIndex-column feature panel.

        Raises:
            ValueError: If the residual panel is empty, has duplicate indexes,
                or optional volume panels cannot be aligned to it.
        """
        self._validate_panel(residual_returns, "residual_returns")
        residual_returns = residual_returns.sort_index().astype(float)
        history = residual_returns.shift(1)

        residual_level = history.rolling(self.level_window, min_periods=self.level_window).sum()
        residual_volatility = history.rolling(self.volatility_window, min_periods=self.volatility_window).std()
        displacement_score = self._rolling_displacement_score(history)
        trend_score, trend_slope, trend_r2 = self._rolling_trend_features(history)
        relative_volume = self._relative_volume(volumes, residual_returns) if volumes is not None else None
        dollar_volume_zscore = (
            self._dollar_volume_zscore(dollar_volumes, residual_returns) if dollar_volumes is not None else None
        )
        ou_s_score, ou_mean_reversion_days = (
            self._rolling_ou_features(history) if self.ou_estimator is not None else (None, None)
        )

        features = self._feature_panel(
            residual_level=residual_level,
            displacement_score=displacement_score,
            trend_score=trend_score,
            trend_slope=trend_slope,
            trend_r2=trend_r2,
            residual_volatility=residual_volatility,
            relative_volume=relative_volume,
            dollar_volume_zscore=dollar_volume_zscore,
            ou_s_score=ou_s_score,
            ou_mean_reversion_days=ou_mean_reversion_days,
        )
        return ResidualStateResult(
            features=features,
            residual_level=residual_level,
            displacement_score=displacement_score,
            trend_score=trend_score,
            trend_slope=trend_slope,
            trend_r2=trend_r2,
            residual_volatility=residual_volatility,
            relative_volume=relative_volume,
            dollar_volume_zscore=dollar_volume_zscore,
            ou_s_score=ou_s_score,
            ou_mean_reversion_days=ou_mean_reversion_days,
        )

    def _rolling_displacement_score(self, history: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(np.nan, index=history.index, columns=history.columns, dtype=float)
        for symbol in history.columns:
            for position in range(self.level_window - 1, len(history)):
                window = history[symbol].iloc[position - self.level_window + 1 : position + 1]
                if window.isna().any():
                    continue
                level = window.cumsum()
                scale = float(level.std(ddof=1))
                if not np.isfinite(scale) or scale == 0.0:
                    continue
                out.iat[position, out.columns.get_loc(symbol)] = (float(level.iloc[-1]) - float(level.mean())) / scale
        return out

    def _rolling_trend_features(self, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        trend_score = pd.DataFrame(np.nan, index=history.index, columns=history.columns, dtype=float)
        trend_slope = trend_score.copy()
        trend_r2 = trend_score.copy()
        x = np.arange(self.trend_window, dtype=float).reshape(-1, 1)
        for symbol in history.columns:
            for position in range(self.trend_window - 1, len(history)):
                window = history[symbol].iloc[position - self.trend_window + 1 : position + 1]
                if window.isna().any():
                    continue
                returns = window.to_numpy(dtype=float)
                level = np.cumsum(returns)
                volatility = float(np.std(returns, ddof=1))
                if not np.isfinite(volatility) or volatility == 0.0:
                    continue
                model = LinearRegression(fit_intercept=True).fit(x, level)
                col = trend_score.columns.get_loc(symbol)
                trend_score.iat[position, col] = (level[-1] - level[0]) / (volatility * np.sqrt(self.trend_window))
                trend_slope.iat[position, col] = float(np.asarray(model.coef_, dtype=float)[0])
                trend_r2.iat[position, col] = float(model.score(x, level))
        return trend_score, trend_slope, trend_r2

    def _rolling_ou_features(self, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        assert self.ou_estimator is not None
        s_scores = pd.DataFrame(np.nan, index=history.index, columns=history.columns, dtype=float)
        mr_days = pd.DataFrame(np.nan, index=history.index, columns=history.columns, dtype=float)
        for symbol in history.columns:
            col = s_scores.columns.get_loc(symbol)
            for position in range(self.level_window - 1, len(history)):
                window = history[symbol].iloc[position - self.level_window + 1 : position + 1]
                if window.isna().any():
                    continue
                estimate = self.ou_estimator.estimate(window)
                if not np.isfinite(estimate.s_score):
                    continue
                s_scores.iat[position, col] = float(estimate.s_score)
                mr_days.iat[position, col] = float(estimate.mean_reversion_days)
        return s_scores, mr_days

    def _relative_volume(self, volumes: pd.DataFrame, residual_returns: pd.DataFrame) -> pd.DataFrame:
        aligned = self._align_optional_panel(volumes, residual_returns, "volumes").shift(1)
        average = aligned.rolling(self.volume_window, min_periods=self.volume_window).mean()
        return aligned.div(average.replace(0.0, np.nan))

    def _dollar_volume_zscore(self, dollar_volumes: pd.DataFrame, residual_returns: pd.DataFrame) -> pd.DataFrame:
        aligned = self._align_optional_panel(dollar_volumes, residual_returns, "dollar_volumes").shift(1)
        average = aligned.rolling(self.volume_window, min_periods=self.volume_window).mean()
        volatility = aligned.rolling(self.volume_window, min_periods=self.volume_window).std()
        return (aligned - average).div(volatility.replace(0.0, np.nan))

    @staticmethod
    def _feature_panel(**panels: pd.DataFrame | None) -> pd.DataFrame:
        blocks: list[pd.DataFrame] = []
        for feature, panel in panels.items():
            if panel is None:
                continue
            block = panel.copy()
            block.columns = pd.MultiIndex.from_product([block.columns.astype(str), [feature]])
            blocks.append(block)
        out = pd.concat(blocks, axis=1).sort_index(axis=1, level=0)
        out.index.name = panels["residual_level"].index.name if panels["residual_level"] is not None else None
        return out

    @staticmethod
    def _align_optional_panel(panel: pd.DataFrame, residual_returns: pd.DataFrame, name: str) -> pd.DataFrame:
        if panel.empty:
            raise ValueError(f"{name} must be non-empty when supplied")
        missing = sorted(set(residual_returns.columns) - set(panel.columns))
        if missing:
            raise ValueError(f"{name} is missing residual-return columns: {missing}")
        return panel.reindex(index=residual_returns.index, columns=residual_returns.columns).astype(float)

    @staticmethod
    def _validate_panel(panel: pd.DataFrame, name: str) -> None:
        if panel.empty:
            raise ValueError(f"{name} must be non-empty")
        if panel.index.has_duplicates:
            raise ValueError(f"{name} index must not contain duplicates")

    @staticmethod
    def _validate_window(value: int, name: str) -> int:
        if value < 2:
            raise ValueError(f"{name} must be >= 2")
        return int(value)
