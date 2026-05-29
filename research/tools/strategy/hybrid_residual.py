from __future__ import annotations

"""Hybrid residual trend/mean-reversion trading rules."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.tools.strategy.base import Strategy
from research.tools.transformer.residual_state import ResidualStateResult


@dataclass(frozen=True)
class HybridResidualSignalResult:
    """Stock-side signals and mode labels from the hybrid residual strategy.

    Attributes:
        signals: Numeric stock-side signals in ``{-1, 0, +1}``.
        modes: String labels: ``"trend"``, ``"mean_reversion"``, or ``"flat"``.
    """

    signals: pd.DataFrame
    modes: pd.DataFrame


class HybridResidualStrategy(Strategy):
    """Choose residual trend-following or mean-reversion by predicted regime.

    ``regime_probabilities`` is interpreted as ``P(trend regime)``. High
    probability activates trend-following when the trend score is strong; low
    probability activates mean reversion when displacement is strong.
    """

    def __init__(
        self,
        trend_probability_entry: float = 0.60,
        trend_probability_exit: float = 0.50,
        mean_reversion_probability_entry: float = 0.40,
        mean_reversion_probability_exit: float = 0.50,
        trend_entry_score: float = 1.0,
        trend_exit_score: float = 0.25,
        mean_reversion_entry_score: float = 1.0,
        mean_reversion_exit_score: float = 0.25,
        min_trend_r2: float | None = None,
        min_relative_volume_for_trend: float | None = None,
        allow_reversal: bool = True,
        mr_score_source: str = "displacement_score",
    ) -> None:
        """Initialize probability, score, and optional confirmation thresholds.

        Args:
            trend_probability_entry: Minimum ``P(trend)`` to open trend trades.
            trend_probability_exit: Trend trades close below this probability.
            mean_reversion_probability_entry: Maximum ``P(trend)`` to open mean-reversion trades.
            mean_reversion_probability_exit: Mean-reversion trades close above this probability.
            trend_entry_score: Minimum absolute trend score for trend entry.
            trend_exit_score: Trend trade closes when absolute trend score falls to or below this value.
            mean_reversion_entry_score: Minimum absolute displacement score for mean-reversion entry.
            mean_reversion_exit_score: Mean-reversion trade closes when absolute displacement falls to or below this value.
            min_trend_r2: Optional minimum trend-line ``R^2`` required for trend entries.
            min_relative_volume_for_trend: Optional minimum relative volume required for trend entries.
            allow_reversal: If true, an active position may switch directly to the other mode.

        Raises:
            ValueError: If threshold ordering is inconsistent.
        """
        if not 0.0 < mean_reversion_probability_entry < mean_reversion_probability_exit <= trend_probability_exit < trend_probability_entry < 1.0:
            raise ValueError(
                "probability thresholds must satisfy 0 < mean_reversion_entry < "
                "mean_reversion_exit <= trend_exit < trend_entry < 1"
            )
        self._validate_score_thresholds(trend_entry_score, trend_exit_score, "trend")
        self._validate_score_thresholds(mean_reversion_entry_score, mean_reversion_exit_score, "mean_reversion")
        if min_trend_r2 is not None and not 0.0 <= min_trend_r2 <= 1.0:
            raise ValueError("min_trend_r2 must be between 0 and 1 when provided")
        if min_relative_volume_for_trend is not None and min_relative_volume_for_trend <= 0.0:
            raise ValueError("min_relative_volume_for_trend must be positive when provided")
        if mr_score_source not in {"displacement_score", "ou_s_score"}:
            raise ValueError("mr_score_source must be 'displacement_score' or 'ou_s_score'")
        self.trend_probability_entry = float(trend_probability_entry)
        self.trend_probability_exit = float(trend_probability_exit)
        self.mean_reversion_probability_entry = float(mean_reversion_probability_entry)
        self.mean_reversion_probability_exit = float(mean_reversion_probability_exit)
        self.trend_entry_score = float(trend_entry_score)
        self.trend_exit_score = float(trend_exit_score)
        self.mean_reversion_entry_score = float(mean_reversion_entry_score)
        self.mean_reversion_exit_score = float(mean_reversion_exit_score)
        self.min_trend_r2 = min_trend_r2
        self.min_relative_volume_for_trend = min_relative_volume_for_trend
        self.allow_reversal = allow_reversal
        self.mr_score_source = mr_score_source

    def generate(self, data: ResidualStateResult, regime_probabilities: pd.DataFrame) -> HybridResidualSignalResult:
        """Generate stateful trend/mean-reversion stock-side signals.

        Args:
            data: Residual state panels from ``ResidualStateTransformer``.
            regime_probabilities: Wide panel of ``P(trend regime)`` values.

        Returns:
            HybridResidualSignalResult containing stock-side signals and mode labels.

        Raises:
            ValueError: If regime probabilities cannot align to the state panels.
        """
        columns = list(data.displacement_score.columns)
        index = data.displacement_score.index
        probabilities = self._align(regime_probabilities, index, columns, "regime_probabilities")
        trend_score = self._align(data.trend_score, index, columns, "trend_score")
        if self.mr_score_source == "ou_s_score":
            if data.ou_s_score is None:
                raise ValueError(
                    "ResidualStateResult.ou_s_score is None; configure the transformer with an OU estimator "
                    "or set mr_score_source='displacement_score'"
                )
            displacement_score = self._align(data.ou_s_score, index, columns, "ou_s_score")
        else:
            displacement_score = self._align(data.displacement_score, index, columns, "displacement_score")
        trend_r2 = self._align(data.trend_r2, index, columns, "trend_r2") if self.min_trend_r2 is not None else None
        relative_volume = (
            self._align(data.relative_volume, index, columns, "relative_volume")
            if self.min_relative_volume_for_trend is not None
            else None
        )

        signals = pd.DataFrame(0.0, index=index, columns=columns)
        modes = pd.DataFrame("flat", index=index, columns=columns)
        for symbol in columns:
            current_signal = 0.0
            current_mode = "flat"
            for timestamp in index:
                trend_entry = self._trend_entry_signal(timestamp, symbol, probabilities, trend_score, trend_r2, relative_volume)
                mr_entry = self._mean_reversion_entry_signal(timestamp, symbol, probabilities, displacement_score)
                if current_mode == "trend":
                    if self._trend_exit(timestamp, symbol, probabilities, trend_score, trend_r2, relative_volume):
                        current_signal, current_mode = self._next_entry(trend_entry, mr_entry)
                    elif self.allow_reversal and mr_entry != 0.0:
                        current_signal, current_mode = mr_entry, "mean_reversion"
                elif current_mode == "mean_reversion":
                    if self._mean_reversion_exit(timestamp, symbol, probabilities, displacement_score):
                        current_signal, current_mode = self._next_entry(trend_entry, mr_entry)
                    elif self.allow_reversal and trend_entry != 0.0:
                        current_signal, current_mode = trend_entry, "trend"
                else:
                    current_signal, current_mode = self._next_entry(trend_entry, mr_entry)
                signals.at[timestamp, symbol] = current_signal
                modes.at[timestamp, symbol] = current_mode
        return HybridResidualSignalResult(signals=signals, modes=modes)

    def _trend_entry_signal(
        self,
        timestamp: object,
        symbol: str,
        probabilities: pd.DataFrame,
        trend_score: pd.DataFrame,
        trend_r2: pd.DataFrame | None,
        relative_volume: pd.DataFrame | None,
    ) -> float:
        probability = float(probabilities.at[timestamp, symbol])
        score = float(trend_score.at[timestamp, symbol])
        if not np.isfinite(probability) or not np.isfinite(score):
            return 0.0
        if probability < self.trend_probability_entry or abs(score) < self.trend_entry_score:
            return 0.0
        if not self._trend_confirmed(timestamp, symbol, trend_r2, relative_volume):
            return 0.0
        return float(np.sign(score))

    def _mean_reversion_entry_signal(
        self,
        timestamp: object,
        symbol: str,
        probabilities: pd.DataFrame,
        displacement_score: pd.DataFrame,
    ) -> float:
        probability = float(probabilities.at[timestamp, symbol])
        score = float(displacement_score.at[timestamp, symbol])
        if not np.isfinite(probability) or not np.isfinite(score):
            return 0.0
        if probability > self.mean_reversion_probability_entry or abs(score) < self.mean_reversion_entry_score:
            return 0.0
        return -float(np.sign(score))

    def _trend_exit(
        self,
        timestamp: object,
        symbol: str,
        probabilities: pd.DataFrame,
        trend_score: pd.DataFrame,
        trend_r2: pd.DataFrame | None,
        relative_volume: pd.DataFrame | None,
    ) -> bool:
        probability = float(probabilities.at[timestamp, symbol])
        score = float(trend_score.at[timestamp, symbol])
        return (
            not np.isfinite(probability)
            or not np.isfinite(score)
            or probability < self.trend_probability_exit
            or abs(score) <= self.trend_exit_score
            or not self._trend_confirmed(timestamp, symbol, trend_r2, relative_volume)
        )

    def _mean_reversion_exit(
        self,
        timestamp: object,
        symbol: str,
        probabilities: pd.DataFrame,
        displacement_score: pd.DataFrame,
    ) -> bool:
        probability = float(probabilities.at[timestamp, symbol])
        score = float(displacement_score.at[timestamp, symbol])
        return (
            not np.isfinite(probability)
            or not np.isfinite(score)
            or probability > self.mean_reversion_probability_exit
            or abs(score) <= self.mean_reversion_exit_score
        )

    def _trend_confirmed(
        self,
        timestamp: object,
        symbol: str,
        trend_r2: pd.DataFrame | None,
        relative_volume: pd.DataFrame | None,
    ) -> bool:
        if trend_r2 is not None:
            value = float(trend_r2.at[timestamp, symbol])
            if not np.isfinite(value) or value < float(self.min_trend_r2):
                return False
        if relative_volume is not None:
            value = float(relative_volume.at[timestamp, symbol])
            if not np.isfinite(value) or value < float(self.min_relative_volume_for_trend):
                return False
        return True

    @staticmethod
    def _next_entry(trend_entry: float, mr_entry: float) -> tuple[float, str]:
        if trend_entry != 0.0:
            return trend_entry, "trend"
        if mr_entry != 0.0:
            return mr_entry, "mean_reversion"
        return 0.0, "flat"

    @staticmethod
    def _align(panel: pd.DataFrame | None, index: pd.Index, columns: list[str], name: str) -> pd.DataFrame:
        if panel is None:
            raise ValueError(f"{name} is required for this strategy configuration")
        missing = sorted(set(columns) - set(panel.columns))
        if missing:
            raise ValueError(f"{name} is missing columns: {missing}")
        return panel.reindex(index=index, columns=columns)

    @staticmethod
    def _validate_score_thresholds(entry: float, exit_: float, name: str) -> None:
        if entry <= 0.0:
            raise ValueError(f"{name}_entry_score must be positive")
        if exit_ < 0.0:
            raise ValueError(f"{name}_exit_score must be non-negative")
        if exit_ >= entry:
            raise ValueError(f"{name}_exit_score must be less than {name}_entry_score")
