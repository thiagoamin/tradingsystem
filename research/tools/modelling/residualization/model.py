from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from research.tools.modelling.residualization.estimators import ExposureEstimator
from research.tools.modelling.residualization.spec import FactorSpec


class FactorResidualizationModel:
    """Residualize stock returns against per-stock factor assignments."""

    def __init__(self, spec: FactorSpec, estimator: ExposureEstimator) -> None:
        """Initialize the model with a factor spec and an exposure estimator."""
        self.spec = spec
        self.estimator = estimator
        self._exposures: pd.DataFrame | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether factor exposures have already been estimated."""
        return self._exposures is not None

    @property
    def exposures(self) -> pd.DataFrame:
        """
        Return a copy of fitted exposures or raise if fit has not been called.
        """
        if self._exposures is None:
            raise RuntimeError("model has not been fitted yet")
        return self._exposures.copy()

    def fit(self, returns: pd.DataFrame) -> FactorResidualizationModel:
        """Estimate per-stock factor betas from a wide returns panel."""
        self._validate_columns(returns)
        exposures = pd.DataFrame(np.nan, index=self.spec.stocks, columns=self.spec.all_factors, dtype=float)
        for stock in self.spec.stocks:
            stock_factors = self.spec.factors_for(stock)
            betas = self.estimator.estimate(returns[stock], returns[stock_factors])
            exposures.loc[stock, stock_factors] = betas.reindex(stock_factors).to_numpy()
        self._exposures = exposures
        return self

    def transform(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Return residual stock returns using betas estimated during fit."""
        if self._exposures is None:
            raise RuntimeError("must call fit() before transform()")
        self._validate_columns(returns)
        residual_cols: dict[str, pd.Series] = {}
        for stock in self.spec.stocks:
            stock_factors = self.spec.factors_for(stock)
            stock_exposures = cast(pd.Series, self._exposures.loc[stock])
            betas = stock_exposures.reindex(stock_factors)
            if betas.isna().any():
                residual_cols[stock] = pd.Series(np.nan, index=returns.index, name=stock, dtype=float)
                continue
            explained = returns[stock_factors].mul(betas.to_numpy(), axis=1).sum(axis=1, min_count=1)
            residual = returns[stock] - explained
            residual.name = stock
            residual_cols[stock] = residual
        out = pd.concat([residual_cols[s] for s in self.spec.stocks], axis=1)
        out.index = returns.index
        return out

    def fit_transform(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Fit exposures on ``returns`` and immediately residualize the same panel."""
        return self.fit(returns).transform(returns)

    def _validate_columns(self, returns: pd.DataFrame) -> None:
        """Validate that all stocks and factors referenced by the spec are present."""
        required = set(self.spec.stocks) | set(self.spec.all_factors)
        missing = sorted(required - set(returns.columns))
        if missing:
            raise ValueError(
                f"returns DataFrame is missing required columns: {missing}. "
                "All stocks and factors in the spec must appear as columns."
            )