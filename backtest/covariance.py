from __future__ import annotations
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class CovarianceEstimator(ABC):
    @abstractmethod
    def estimate(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Return an (n x n) covariance matrix from a returns DataFrame.
        """
        ...


class SampleCovariance(CovarianceEstimator):
    """
    Plain sample covariance matrix.
    """

    def estimate(self, returns: pd.DataFrame) -> np.ndarray:
        return returns.cov().values


class LedoitWolfShrinkage(CovarianceEstimator):
    """
    Constant-correlation shrinkage target (manual Ledoit-Wolf).
    """

    def __init__(self, delta: float = 0.4):
        self.delta = delta

    def estimate(self, returns: pd.DataFrame) -> np.ndarray:
        S = returns.cov().values
        n = S.shape[0]
        std = np.sqrt(np.diag(S))
        corr = S / np.outer(std, std)
        avg_corr = (corr.sum() - n) / (n * (n - 1))
        F = avg_corr * np.outer(std, std)
        np.fill_diagonal(F, np.diag(S))
        return self.delta * F + (1 - self.delta) * S
