from __future__ import annotations

import pandas as pd

from research.tools.transformer.base import PanelTransformer
from research.tools.transformer.residualization.rolling_estimators import RollingExposureEstimator
from research.tools.transformer.residualization.spec import FactorSpec


class RollingFactorResidualizationModel(PanelTransformer):
    """Stub orchestration class for time-varying factor residualization."""

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
        raise NotImplementedError("Rolling factor residualization fit has not been implemented yet.")

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Residualize returns using previously estimated rolling beta paths."""
        raise NotImplementedError("Rolling factor residualization transform has not been implemented yet.")
