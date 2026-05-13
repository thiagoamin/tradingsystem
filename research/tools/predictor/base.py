from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PanelPredictor(ABC):
    """Base interface for models that learn from panel features and predict panel outputs."""

    @abstractmethod
    def fit(self, features: pd.DataFrame, target: pd.DataFrame | pd.Series) -> PanelPredictor:
        """Fit the predictor on panel features and target data and return self."""

    @abstractmethod
    def predict(self, features: pd.DataFrame) -> pd.DataFrame | pd.Series:
        """Generate out-of-sample predictions from panel features."""
