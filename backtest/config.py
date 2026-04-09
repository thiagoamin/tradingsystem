from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class BacktestConfig:
    """
    Parameters
    """
    assets: List[str]

    cov_lookback: int = 126          
    shrinkage_delta: float = 0.2     

    gamma_normal: float = 2.0
    gamma_riskoff: float = 4.0

    kappa: float = 0.5               
    eta: float = 0.001               
    max_weight: float = 0.35         

    target_vol: float = 0.14        

    tau: float = 0.05                
    c_signal: float = 0.05          

    rebal_freq: str = "ME"
    min_history: int = 252           

    mom_windows: List[int] = field(default_factory=lambda: [21, 63, 126, 252])
    mom_weights: List[float] = field(default_factory=lambda: [0.0, 0.2, 0.3, 0.5])
    beta_rev: float = 0.05         

    trend_asset: str = "SPY"         
    ma_window: int = 200             #MA look-back
    corr_thresh_lo: float = 0.35     #avg pairwise corr below → risk-on
    corr_thresh_hi: float = 0.70     #avg pairwise corr above → risk-off

    defensive_assets: List[str] = field(default_factory=lambda: ["TLT", "GLD"])
    riskoff_boost: float = 0.005      
    riskoff_dampen: float = 0.002     
