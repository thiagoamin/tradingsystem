from __future__ import annotations

"""Paper-style rolling OU signals from stock returns and assigned ETF factors."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from research.tools.transformer.mean_reversion.ou_estimator import OUEstimator
from research.tools.transformer.residualization import FactorSpec


@dataclass(frozen=True)
class FactorOUScoreResult:
    """Daily OU signals, eligibility, fitted betas, and parameter records."""

    scores: pd.DataFrame
    eligibility: pd.DataFrame
    factor_betas: dict[str, pd.DataFrame]
    parameters: pd.DataFrame


class RollingAssignedEtfOUScoreModel:
    """Estimate the Avellaneda--Lee assigned-ETF signal with no lookahead.

    Each stock must have exactly one assigned ETF. For decision date ``t``,
    its beta and OU model are fitted from the preceding ``window`` returns
    only. Beta follows the paper's single-ETF covariance/variance equation;
    the residual passed to the pure mean-reversion model is
    ``stock_return - beta * etf_return``.
    """

    def __init__(self, spec: FactorSpec, window: int = 60, estimator: OUEstimator | None = None) -> None:
        """Initialize assigned ETF mappings and trailing signal window."""
        if window < 3:
            raise ValueError("window must be >= 3")
        for stock in spec.stocks:
            if len(spec.factors_for(stock)) != 1:
                raise ValueError("each stock must have exactly one assigned ETF factor")
        self.spec = spec
        self.window = window
        self.estimator = estimator or OUEstimator()

    def transform(self, returns: pd.DataFrame) -> FactorOUScoreResult:
        """Return lagged beta and OU signal paths for a chronological return panel.

        Raises:
            ValueError: If required columns are absent, timestamps duplicate,
                or the input panel is empty.
        """
        self._validate_returns(returns)
        returns = returns.sort_index()
        stocks = self.spec.stocks
        scores = pd.DataFrame(np.nan, index=returns.index, columns=stocks, dtype=float)
        eligible = pd.DataFrame(False, index=returns.index, columns=stocks, dtype=bool)
        betas = {
            factor: pd.DataFrame(0.0, index=returns.index, columns=stocks, dtype=float)
            for factor in self.spec.all_factors
        }
        records: list[dict[str, object]] = []

        for position in range(self.window, len(returns)):
            timestamp = returns.index[position]
            history = returns.iloc[position - self.window : position]
            for stock in stocks:
                factor = self.spec.factors_for(stock)[0]
                sample = history[[stock, factor]].dropna()
                if len(sample) < self.window:
                    continue
                beta = self._single_factor_beta(sample[stock], sample[factor])
                if beta is None:
                    continue
                betas[factor].at[timestamp, stock] = beta
                residuals = sample[stock] - beta * sample[factor]
                estimate = self.estimator.estimate(residuals)
                scores.at[timestamp, stock] = estimate.s_score
                eligible.at[timestamp, stock] = estimate.eligible
                records.append({"timestamp": timestamp, "symbol": stock, "factor": factor, "beta": beta, **asdict(estimate)})

        parameters = pd.DataFrame.from_records(records)
        if not parameters.empty:
            parameters = parameters.set_index(["timestamp", "symbol"]).sort_index()
        return FactorOUScoreResult(scores, eligible, betas, parameters)

    @staticmethod
    def _single_factor_beta(stock_returns: pd.Series, factor_returns: pd.Series) -> float | None:
        factor_variance = float(factor_returns.var())
        if not np.isfinite(factor_variance) or factor_variance <= 0:
            return None
        beta = float(stock_returns.cov(factor_returns) / factor_variance)
        return beta if np.isfinite(beta) else None

    def _validate_returns(self, returns: pd.DataFrame) -> None:
        if returns.empty:
            raise ValueError("returns must be non-empty")
        if returns.index.has_duplicates:
            raise ValueError("returns index must not contain duplicates")
        required = set(self.spec.stocks) | set(self.spec.all_factors)
        missing = sorted(required - set(returns.columns))
        if missing:
            raise ValueError(f"returns DataFrame is missing required columns: {missing}")
