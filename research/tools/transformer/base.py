from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Transformer(ABC):
    """Base interface for models that transform one panel into another."""

    @abstractmethod
    def fit(self, data: pd.DataFrame) -> Transformer:
        """Fit the transformer on a panel of data and return self."""

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform a panel using parameters estimated during fit."""

    def fit_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Fit the transformer and immediately transform the same panel."""
        return self.fit(data).transform(data)


PanelTransformer = Transformer

__all__ = ["PanelTransformer", "Transformer"]
