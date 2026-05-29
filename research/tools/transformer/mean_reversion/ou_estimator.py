from __future__ import annotations

"""Ornstein--Uhlenbeck estimation from cumulative residual returns."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


@dataclass(frozen=True)
class OUEstimate:
    """Estimated OU parameters and s-score for one residual-return window."""

    ar_intercept: float
    ar_coef: float
    kappa_per_year: float
    equilibrium_mean: float
    equilibrium_vol: float
    mean_reversion_days: float
    s_score: float
    eligible: bool
    status: str


class OUEstimator:
    """Estimate an OU mean-reversion model from one residual-return window."""

    def __init__(self, periods_per_year: int = 252, max_mean_reversion_days: float = 30.0) -> None:
        """Initialize the estimator and eligibility threshold."""
        if periods_per_year < 1:
            raise ValueError("periods_per_year must be >= 1")
        if max_mean_reversion_days <= 0:
            raise ValueError("max_mean_reversion_days must be positive")
        self.periods_per_year = periods_per_year
        self.max_mean_reversion_days = float(max_mean_reversion_days)

    def estimate(self, residual_returns: pd.Series) -> OUEstimate:
        """Estimate OU parameters and the terminal s-score.

        Args:
            residual_returns: Complete trailing residual-return window. Its
                cumulative sum is interpreted as the residual level.

        Returns:
            Estimated parameters. Nonstationary or degenerate fits are marked
            ineligible and expose ``NaN`` transformed quantities.

        Raises:
            ValueError: If fewer than three complete observations are supplied.
        """
        if len(residual_returns) < 3 or residual_returns.isna().any():
            raise ValueError("residual_returns must contain at least three complete observations")

        level = residual_returns.astype(float).cumsum()
        x = level.iloc[:-1].to_numpy(dtype=float).reshape(-1, 1)
        y = level.iloc[1:].to_numpy(dtype=float)
        model = LinearRegression(fit_intercept=True).fit(x, y)
        ar_coef = float(np.asarray(model.coef_)[0])
        ar_intercept = float(model.intercept_)

        if not 0.0 < ar_coef < 1.0:
            return self._invalid(ar_intercept, ar_coef, "non_stationary_ar_coef")

        innovation = y - model.predict(x)
        innovation_vol = float(np.sqrt(np.sum(innovation**2) / max(len(innovation) - 2, 1)))
        denominator = float(np.sqrt(1.0 - ar_coef**2))
        equilibrium_vol = innovation_vol / denominator
        if not np.isfinite(equilibrium_vol) or equilibrium_vol <= 0:
            return self._invalid(ar_intercept, ar_coef, "invalid_equilibrium_vol")

        kappa = -float(np.log(ar_coef)) * self.periods_per_year
        equilibrium_mean = ar_intercept / (1.0 - ar_coef)
        mean_reversion_days = self.periods_per_year / kappa
        s_score = (float(level.iloc[-1]) - equilibrium_mean) / equilibrium_vol
        eligible = mean_reversion_days < self.max_mean_reversion_days
        status = "eligible" if eligible else "slow_mean_reversion"
        return OUEstimate(
            ar_intercept=ar_intercept,
            ar_coef=ar_coef,
            kappa_per_year=kappa,
            equilibrium_mean=equilibrium_mean,
            equilibrium_vol=equilibrium_vol,
            mean_reversion_days=mean_reversion_days,
            s_score=s_score,
            eligible=eligible,
            status=status,
        )

    @staticmethod
    def _invalid(ar_intercept: float, ar_coef: float, status: str) -> OUEstimate:
        nan = float("nan")
        return OUEstimate(ar_intercept, ar_coef, nan, nan, nan, nan, nan, False, status)
