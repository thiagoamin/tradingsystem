from __future__ import annotations

"""Backtest the paper-style assigned-sector-ETF daily s-score strategy."""

from pathlib import Path

import pandas as pd

from research.tools.backtest import FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.processing import DailyEodPanels
from research.tools.strategy import OUSScoreStrategy
from research.tools.transformer.mean_reversion import OUEstimator, RollingAssignedEtfOUScoreModel
from research.tools.transformer.residualization import FactorSpec

from .config import FACTOR_ETFS, SECTOR_STOCKS, STOCKS, STOCK_TO_ETF, TRADING_START_DATE
from .ingest_theta_eod_data import load_or_fetch_panels

ESTIMATION_WINDOW = 60
MAX_MEAN_REVERSION_DAYS = 30.0
STOCK_WEIGHT = 0.05
GROSS_EXPOSURE_LIMIT = 2.0
TRANSACTION_COST_BPS = 5.0
HEDGE_FRACTION = 1.0
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "sector_etf"
    / "s_score_backtest"
)


def run(refresh_data: bool = False, output_root: Path = OUTPUT_ROOT) -> pd.DataFrame:
    """Load or fetch input data and save sector-ETF strategy outputs."""
    return build_outputs(load_or_fetch_panels(refresh_data=refresh_data), output_root=output_root)


def build_outputs(panels: DailyEodPanels, output_root: Path = OUTPUT_ROOT) -> pd.DataFrame:
    """Estimate paper-style signals and backtest their ETF-hedged portfolio.

    At each decision date, the beta and OU fit use only the preceding 60
    returns. Each stock is regressed only against its assigned sector ETF.
    """
    estimator = RollingAssignedEtfOUScoreModel(
        spec=FactorSpec({stock: [etf] for stock, etf in STOCK_TO_ETF.items()}),
        window=ESTIMATION_WINDOW,
        estimator=OUEstimator(max_mean_reversion_days=MAX_MEAN_REVERSION_DAYS),
    )
    estimated = estimator.transform(panels.returns)
    start = pd.Timestamp(TRADING_START_DATE)
    scores = estimated.scores.loc[start:, STOCKS]
    eligibility = estimated.eligibility.loc[start:, STOCKS]
    signals = OUSScoreStrategy().generate(scores, eligibility=eligibility)
    betas = {factor: panel.reindex(signals.index) for factor, panel in estimated.factor_betas.items()}
    returns = panels.returns.reindex(signals.index).loc[:, STOCKS + FACTOR_ETFS]
    engine = FactorHedgedDailyBacktestEngine(
        stock_weight=STOCK_WEIGHT,
        gross_exposure_limit=GROSS_EXPOSURE_LIMIT,
        transaction_cost_bps=TRANSACTION_COST_BPS,
        hedge_fraction=HEDGE_FRACTION,
    )
    result = engine.run(stock_signals=signals, returns=returns, factor_betas=betas)
    evaluator = BasicStrategyEvaluator(annualization_factor=252)
    metrics = evaluator.evaluate(result.portfolio_pnl["net_pnl"], positions=result.target_weights)

    output_root.mkdir(parents=True, exist_ok=True)
    scores.to_csv(output_root / "s_scores.csv")
    eligibility.to_csv(output_root / "eligibility.csv")
    _parameters_after(estimated.parameters, start).to_csv(output_root / "ou_parameters_and_betas.csv")
    signals.to_csv(output_root / "stock_signals.csv")
    result.target_weights.to_csv(output_root / "target_weights.csv")
    result.asset_pnl.to_csv(output_root / "asset_pnl.csv")
    result.portfolio_pnl.to_csv(output_root / "portfolio_pnl.csv")
    result.exposure_diagnostics.to_csv(output_root / "exposure_diagnostics.csv")
    _sector_pnl(result).to_csv(output_root / "sector_pnl.csv")
    _stock_activity(signals).to_csv(output_root / "stock_activity.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "specification": "assigned_sector_etf",
                "stock_count": len(STOCKS),
                "sector_etf_count": len(FACTOR_ETFS),
                "window_days": ESTIMATION_WINDOW,
                "stock_weight": STOCK_WEIGHT,
                "gross_exposure_limit": GROSS_EXPOSURE_LIMIT,
                "transaction_cost_bps": TRANSACTION_COST_BPS,
                "hedge_fraction": HEDGE_FRACTION,
                **metrics,
                "split_adjusted": panels.split_adjusted,
                "dividend_adjusted": panels.dividend_adjusted,
                "corporate_action_adjusted": panels.corporate_action_adjusted,
            }
        ]
    )
    summary.to_csv(output_root / "strategy_summary.csv", index=False)
    return summary


def _sector_pnl(result: FactorHedgedBacktestResult) -> pd.DataFrame:
    output: dict[str, pd.Series] = {}
    cost_rate = TRANSACTION_COST_BPS / 10_000.0
    for factor, stocks in SECTOR_STOCKS.items():
        columns = list(stocks) + [factor]
        gross = result.asset_pnl[columns].sum(axis=1)
        turnover = (
            result.target_weights[columns]
            .diff()
            .fillna(result.target_weights[columns])
            .abs()
            .sum(axis=1)
        )
        output[factor] = gross - turnover * cost_rate
    return pd.DataFrame(output)


def _parameters_after(parameters: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    if parameters.empty:
        return parameters
    timestamps = parameters.index.get_level_values("timestamp")
    return parameters.loc[timestamps >= start]


def _stock_activity(signals: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": stock,
                "sector_etf": STOCK_TO_ETF[stock],
                "active_days": int(signals[stock].ne(0.0).sum()),
                "long_days": int(signals[stock].gt(0.0).sum()),
                "short_days": int(signals[stock].lt(0.0).sum()),
            }
            for stock in STOCKS
        ]
    )


if __name__ == "__main__":
    strategy_summary = run()
    print(strategy_summary.to_string(index=False))
    print(f"Saved assigned-sector-ETF outputs to {OUTPUT_ROOT}")
