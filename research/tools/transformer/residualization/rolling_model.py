from __future__ import annotations

import pandas as pd

from research.tools.transformer.base import PanelTransformer
from research.tools.transformer.residualization.rolling_estimators import RollingExposureEstimator
from research.tools.transformer.residualization.spec import FactorSpec


class RollingFactorResidualizationModel(PanelTransformer):
    """Residualize each return using lagged rolling factor exposures.

    The supplied panel is used to construct a beta path. Exposure at each row
    is estimated only from earlier rows, so ``fit_transform`` is safe for a
    chronologically ordered out-of-sample residual path.
    """

    def __init__(self, spec: FactorSpec, estimator: RollingExposureEstimator) -> None:
        self.spec = spec
        self.estimator = estimator
        self._exposure_paths: dict[str, pd.DataFrame] | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether rolling exposure paths have been estimated."""
        return self._exposure_paths is not None

    @property
    def exposure_paths(self) -> dict[str, pd.DataFrame]:
        """Return a copy of the fitted rolling exposure paths."""
        if self._exposure_paths is None:
            raise RuntimeError("model has not been fitted yet")
        return {stock: path.copy() for stock, path in self._exposure_paths.items()}

    def fit(self, data: pd.DataFrame) -> RollingFactorResidualizationModel:
        """Estimate rolling beta paths for each stock in the factor spec."""
        self._validate_columns(data)
        self._exposure_paths = {
            stock: self.estimator.estimate_path(data[stock], data[self.spec.factors_for(stock)])
            for stock in self.spec.stocks
        }
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Residualize returns using beta estimates known before each row."""
        if self._exposure_paths is None:
            raise RuntimeError("must call fit() before transform()")
        self._validate_columns(data)

        residuals: dict[str, pd.Series] = {}
        for stock in self.spec.stocks:
            factors = self.spec.factors_for(stock)
            path = self._exposure_paths[stock]
            missing_dates = data.index.difference(path.index)
            if not missing_dates.empty:
                raise ValueError(
                    "transform data contains dates without fitted rolling exposures; "
                    "fit on the full chronological panel before transforming it"
                )
            aligned_path = path.reindex(data.index)
            betas = aligned_path[factors]
            explained = (data[factors] * betas).sum(axis=1, min_count=len(factors))
            if "alpha" in aligned_path:
                explained = explained + aligned_path["alpha"]
            residuals[stock] = (data[stock] - explained).rename(stock)
        return pd.DataFrame(residuals, index=data.index)

    def _validate_columns(self, data: pd.DataFrame) -> None:
        required = set(self.spec.stocks) | set(self.spec.all_factors)
        missing = sorted(required - set(data.columns))
        if missing:
            raise ValueError(f"returns DataFrame is missing required columns: {missing}")
