from __future__ import annotations

"""Rolling OU/s-score transformation for residual-return panels."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from research.tools.transformer.mean_reversion.ou_estimator import OUEstimate, OUEstimator


@dataclass(frozen=True)
class OUScoreResult:
    """Time-indexed s-scores, eligibility flags, and OU parameter records."""

    scores: pd.DataFrame
    eligibility: pd.DataFrame
    parameters: pd.DataFrame


class RollingOUScoreModel:
    """Estimate lagged OU models and produce daily s-score paths."""

    def __init__(self, window: int = 60, estimator: OUEstimator | None = None) -> None:
        """Initialize a trailing-window OU score model."""
        if window < 3:
            raise ValueError("window must be >= 3")
        self.window = window
        self.estimator = estimator or OUEstimator()

    def transform(self, residual_returns: pd.DataFrame) -> OUScoreResult:
        """Produce no-lookahead s-score and eligibility paths.

        At row ``t``, estimation uses only the ``window`` residual returns
        ending at row ``t - 1``.

        Args:
            residual_returns: Wide chronological residual-return panel.

        Returns:
            Score and eligibility panels aligned to the input, plus one
            parameter record for each date/symbol with a complete fit window.

        Raises:
            ValueError: If the residual panel is empty or has duplicate dates.
        """
        if residual_returns.empty:
            raise ValueError("residual_returns must be non-empty")
        if residual_returns.index.has_duplicates:
            raise ValueError("residual_returns index must not contain duplicates")

        residual_returns = residual_returns.sort_index()
        scores = pd.DataFrame(np.nan, index=residual_returns.index, columns=residual_returns.columns, dtype=float)
        eligible = pd.DataFrame(False, index=residual_returns.index, columns=residual_returns.columns, dtype=bool)
        records: list[dict[str, object]] = []

        for position in range(self.window, len(residual_returns)):
            window = residual_returns.iloc[position - self.window : position]
            timestamp = residual_returns.index[position]
            for symbol in residual_returns.columns:
                series = window[symbol]
                if series.isna().any():
                    continue
                estimate = self.estimator.estimate(series)
                scores.loc[timestamp, symbol] = estimate.s_score
                eligible.loc[timestamp, symbol] = estimate.eligible
                records.append(self._parameter_record(timestamp, str(symbol), estimate))

        parameters = pd.DataFrame.from_records(records)
        if not parameters.empty:
            parameters = parameters.set_index(["timestamp", "symbol"]).sort_index()
        return OUScoreResult(scores=scores, eligibility=eligible, parameters=parameters)

    @staticmethod
    def _parameter_record(timestamp: object, symbol: str, estimate: OUEstimate) -> dict[str, object]:
        return {"timestamp": timestamp, "symbol": symbol, **asdict(estimate)}
