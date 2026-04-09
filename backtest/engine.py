from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import BacktestConfig
from .covariance import CovarianceEstimator, LedoitWolfShrinkage
from .metrics import MetricSet, calc_metrics
from .optimizer import BlackLittermanMVOptimizer, WeightOptimizer
from .regime import MACorrelationDetector, RegimeDetector
from .signals import MomentumReversalSignal, PortfolioSignal


def _vol_target_scale(w: np.ndarray, sigma: np.ndarray, target: float) -> tuple[np.ndarray, float]:
    """
    Scale weights so the portfolio hits target annualised vol.
    """
    port_vol = float(np.sqrt(w @ (sigma * 252) @ w))
    if port_vol < 1e-8:
        return w, 0.0
    scale = min(1.0, target / port_vol)
    return w * scale, port_vol


@dataclass
class BacktestResult:
    """
    Output of a single backtest run.
    """

    port_df: pd.DataFrame
    weights_df: pd.DataFrame

    def metrics(self, label: str = "Portfolio") -> MetricSet:
        return calc_metrics(self.port_df["port_ret"], label)

    def benchmark_metrics(self) -> List[MetricSet]:
        out = []
        if "spy_ret" in self.port_df.columns:
            out.append(calc_metrics(self.port_df["spy_ret"].dropna(), "SPY B&H"))
        if "ew_ret" in self.port_df.columns:
            out.append(calc_metrics(self.port_df["ew_ret"].dropna(), "Equal-Weight"))
        return out

    def summary(self) -> pd.DataFrame:
        """Return a tidy summary DataFrame (strategy + benchmarks)."""
        rows = [self.metrics()] + self.benchmark_metrics()
        return pd.DataFrame([
            {
                "Strategy":  m.label,
                "CAGR":      f"{m.cagr:+.2%}",
                "Vol":       f"{m.vol:.2%}",
                "Sharpe":    f"{m.sharpe:.2f}",
                "Max DD":    f"{m.max_drawdown:.2%}",
            }
            for m in rows
        ])

    def print_report(self) -> None:
        """Print a formatted performance report to stdout."""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        for m in [self.metrics()] + self.benchmark_metrics():
            print(m)
        if "regime" in self.weights_df.columns:
            print(f"\nRegime distribution:\n{self.weights_df['regime'].value_counts().to_string()}")
        if "n_eff" in self.weights_df.columns:
            print(f"Avg effective bets : {self.weights_df['n_eff'].mean():.1f}")
        print("=" * 60)


def run_backtest(close: pd.DataFrame, config: BacktestConfig,*, cov_estimator: Optional[CovarianceEstimator] = None,
    signal: Optional[PortfolioSignal] = None, regime_detector: Optional[RegimeDetector] = None, 
    optimizer: Optional[WeightOptimizer] = None, benchmarks: bool = True) -> BacktestResult:
    """
    Run a portfolio backtest on a wide close-price DataFrame.
    """
    assets = config.assets
    close = close[assets].dropna().copy()

    if len(close) < config.min_history + 1:
        raise ValueError(
            f"Not enough history: need ≥ {config.min_history + 1} rows, got {len(close)}."
        )
    
    if cov_estimator is None:
        cov_estimator = LedoitWolfShrinkage(delta=config.shrinkage_delta)

    if signal is None:
        signal = MomentumReversalSignal(
            mom_windows=config.mom_windows,
            mom_weights=config.mom_weights,
            beta_rev=config.beta_rev,
            c_signal=config.c_signal,
        )

    trend_asset = config.trend_asset if config.trend_asset in assets else assets[0]
    if regime_detector is None:
        regime_detector = MACorrelationDetector(
            corr_thresh_lo=config.corr_thresh_lo,
            corr_thresh_hi=config.corr_thresh_hi,
            ma_window=config.ma_window,
            trend_asset=trend_asset,
        )

    if optimizer is None:
        optimizer = BlackLittermanMVOptimizer(
            tau=config.tau,
            gamma_normal=config.gamma_normal,
            gamma_riskoff=config.gamma_riskoff,
            kappa=config.kappa,
            eta=config.eta,
            max_weight=config.max_weight,
            assets=assets,
            defensive_assets=config.defensive_assets,
            riskoff_boost=config.riskoff_boost,
            riskoff_dampen=config.riskoff_dampen,
        )

    returns = close.pct_change().dropna()
    first_valid = close.index[config.min_history]

    try:
        month_ends = returns.resample(config.rebal_freq).last().loc[first_valid:].index
    except ValueError:
        month_ends = returns.resample("M").last().loc[first_valid:].index

    month_ends = month_ends[month_ends.isin(returns.index)]

    n = len(assets)
    prev_w = np.full(n, 1.0 / n)
    records = []

    for dt in month_ends:
        loc = close.index.get_loc(dt)
        ret_window = returns.iloc[max(0, loc - config.cov_lookback) : loc + 1]
        if len(ret_window) < 60:
            continue

        sigma      = cov_estimator.estimate(ret_window)
        signal_mu  = signal.compute(close, dt, assets)
        regime     = regime_detector.detect(close, dt, sigma, assets)
        w          = optimizer.optimize(signal_mu, sigma, prev_w, regime)
        w_final, port_vol = _vol_target_scale(w, sigma, config.target_vol)

        cash_wt = 1.0 - w_final.sum()
        gamma   = config.gamma_riskoff if regime == "risk-off" else config.gamma_normal
        w2_sum  = float((w_final ** 2).sum())
        n_eff   = 1.0 / w2_sum if w2_sum > 0 else 0.0

        records.append({
            "date":         dt,
            "regime":       regime,
            "gamma":        gamma,
            "port_vol_ann": port_vol,
            "cash":         cash_wt,
            "n_eff":        n_eff,
            **{f"w_{a}": float(w_final[i]) for i, a in enumerate(assets)},
        })
        prev_w = w 

    weights_df = pd.DataFrame(records).set_index("date")

    wt_cols = [f"w_{a}" for a in assets]
    port_rets: list[dict] = []

    for i in range(len(weights_df)):
        dt      = weights_df.index[i]
        next_dt = weights_df.index[i + 1] if i + 1 < len(weights_df) else returns.index[-1]
        mask    = (returns.index > dt) & (returns.index <= next_dt)
        period  = returns.loc[mask, assets]
        w_vec   = weights_df.iloc[i][wt_cols].values.astype(float)
        daily   = period.values @ w_vec
        port_rets.extend({"date": d, "port_ret": r} for d, r in zip(period.index, daily))

    port_df = pd.DataFrame(port_rets).set_index("date")
    port_df["cum_ret"] = (1 + port_df["port_ret"]).cumprod()

    if benchmarks and not port_df.empty:
        start = port_df.index[0]
        if "SPY" in returns.columns:
            spy = returns["SPY"].loc[start:]
            port_df["spy_ret"] = spy
            port_df["spy_cum"] = (1 + spy).cumprod()
        ew = returns[assets].mean(axis=1).loc[start:]
        port_df["ew_ret"] = ew
        port_df["ew_cum"] = (1 + ew).cumprod()

    return BacktestResult(port_df=port_df, weights_df=weights_df)
