from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Set

import numpy as np
from scipy.optimize import minimize


class WeightOptimizer(ABC):
    @abstractmethod
    def optimize(self, signal_mu: np.ndarray, sigma: np.ndarray, 
                 prev_w: np.ndarray, regime: str = "neutral") -> np.ndarray:
        """
        Return target portfolio weights.
        """
        ...

class EqualWeightOptimizer(WeightOptimizer):
    """ 
    Performance floor benchmark.
    """

    def optimize(self, signal_mu, sigma, prev_w, regime="neutral") -> np.ndarray:
        n = len(signal_mu)
        return np.full(n, 1.0 / n)

class BlackLittermanMVOptimizer(WeightOptimizer):
    """
    Black-Litterman posterior blending + mean-variance optimisation.
    """

    def __init__(self, tau: float = 0.05, gamma_normal: float = 4.0, gamma_riskoff: float = 8.0,
        kappa: float = 5.0, eta: float = 0.005, max_weight: float = 0.25, assets: Optional[List[str]] = None,
        defensive_assets: Optional[List[str]] = None, riskoff_boost: float = 0.01, riskoff_dampen: float = 0.005):
        self.tau = tau
        self.gamma_normal = gamma_normal
        self.gamma_riskoff = gamma_riskoff
        self.kappa = kappa
        self.eta = eta
        self.max_weight = max_weight
        self.assets: List[str] = assets or []
        self.defensive: Set[str] = set(defensive_assets or [])
        self.riskoff_boost = riskoff_boost
        self.riskoff_dampen = riskoff_dampen

    def _bl_posterior(self, signal_mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        n = sigma.shape[0]
        inv_vol = 1.0 / np.sqrt(np.diag(sigma) * 252)
        pi = 0.05 * inv_vol / inv_vol.sum()

        tau_sigma_inv = np.linalg.inv(self.tau * sigma)
        omega_inv = np.diag(1.0 / np.diag(self.tau * sigma))   # diag → cheap inversion
        M = np.linalg.inv(tau_sigma_inv + omega_inv)            # P = I so P'Ω⁻¹P = Ω⁻¹
        return M @ (tau_sigma_inv @ pi + omega_inv @ signal_mu)


    def _adjust_signal(self, signal_mu: np.ndarray, regime: str) -> np.ndarray:
        if regime != "risk-off":
            return signal_mu
        mu = signal_mu.copy()
        for i, asset in enumerate(self.assets):
            if asset in self.defensive:
                mu[i] += self.riskoff_boost
            else:
                mu[i] -= self.riskoff_dampen
        return mu

    def _mv_optimise(self, mu_bl: np.ndarray, sigma: np.ndarray, prev_w: np.ndarray, gamma: float) -> np.ndarray:
        
        def neg_utility(w: np.ndarray) -> float:
            ret  = w @ mu_bl
            risk = 0.5 * gamma * w @ sigma_ann @ w
            conc = self.kappa * (w ** 2).sum()
            turn = self.eta * np.abs(w - prev_w).sum()
            return -(ret - risk - conc - turn)
        
        n = len(mu_bl)
        sigma_ann = sigma * 252

        x0 = np.full(n, 1.0 / n)
        res = minimize(neg_utility, x0, method="SLSQP", bounds=[(0.0, self.max_weight)] * n, constraints={"type": "eq", "fun": lambda w: w.sum() - 1.0}, options={"maxiter": 1000, "ftol": 1e-12},
        )
        return res.x if res.success else x0
    
    def optimize(self, signal_mu: np.ndarray, sigma: np.ndarray, prev_w: np.ndarray, regime: str = "neutral") -> np.ndarray:
        gamma = self.gamma_riskoff if regime == "risk-off" else self.gamma_normal
        adjusted_mu = self._adjust_signal(signal_mu, regime)
        mu_bl = self._bl_posterior(adjusted_mu, sigma)
        return self._mv_optimise(mu_bl, sigma, prev_w, gamma)