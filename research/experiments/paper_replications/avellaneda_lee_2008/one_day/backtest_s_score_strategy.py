from __future__ import annotations

"""Backtest the daily OU s-score strategy with split-adjusted ETF hedges."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.tools.backtest import FactorHedgedDailyBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.processing import DailyEodPanels
from research.tools.strategy import OUSScoreStrategy
from research.tools.transformer.mean_reversion import OUEstimator, RollingOUScoreModel

from .estimate_ou_scores import MAX_MEAN_REVERSION_DAYS, SCORE_START_DATE
from .ingest_theta_eod_data import END_DATE, START_DATE, TECH_STOCKS, run as ingest_eod
from .rolling_etf_residualization import ESTIMATION_WINDOW, FACTOR_SPECS, build_residual_paths

STOCK_WEIGHT = 0.05
GROSS_EXPOSURE_LIMIT = 2.0
TRANSACTION_COST_BPS = 5.0
HEDGE_FRACTION = 1.0
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "s_score_backtest"
)


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    trading_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Fetch ThetaData inputs and save split-adjusted strategy/backtest outputs."""
    panels = ingest_eod(start_date=start_date, end_date=end_date)
    return build_outputs(panels, trading_start_date=trading_start_date, output_root=output_root)


def build_outputs(
    panels: DailyEodPanels,
    trading_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Compute stateful s-score signals, ETF hedges, net PnL, and metrics."""
    strategy = OUSScoreStrategy()
    scorer = RollingOUScoreModel(
        window=ESTIMATION_WINDOW,
        estimator=OUEstimator(max_mean_reversion_days=MAX_MEAN_REVERSION_DAYS),
    )
    backtest = FactorHedgedDailyBacktestEngine(
        stock_weight=STOCK_WEIGHT,
        gross_exposure_limit=GROSS_EXPOSURE_LIMIT,
        transaction_cost_bps=TRANSACTION_COST_BPS,
        hedge_fraction=HEDGE_FRACTION,
    )
    evaluator = BasicStrategyEvaluator(annualization_factor=252)
    output_root.mkdir(parents=True, exist_ok=True)
    start_timestamp = pd.Timestamp(trading_start_date)
    summary_rows: list[dict[str, object]] = []

    for label, (residuals, exposures) in build_residual_paths(panels).items():
        factors = FACTOR_SPECS[label]
        ou_result = scorer.transform(residuals)
        scores = ou_result.scores.loc[start_timestamp:, TECH_STOCKS]
        eligibility = ou_result.eligibility.loc[start_timestamp:, TECH_STOCKS]
        signals = strategy.generate(scores, eligibility=eligibility)
        betas = _factor_beta_panels(exposures.reindex(signals.index), factors)
        returns = panels.returns.reindex(signals.index).loc[:, TECH_STOCKS + factors]
        result = backtest.run(stock_signals=signals, returns=returns, factor_betas=betas)
        metrics = evaluator.evaluate(result.portfolio_pnl["net_pnl"], positions=result.target_weights)

        specification_root = output_root / label
        specification_root.mkdir(parents=True, exist_ok=True)
        signals.to_csv(specification_root / "stock_signals.csv")
        result.target_weights.to_csv(specification_root / "target_weights.csv")
        result.asset_pnl.to_csv(specification_root / "asset_pnl.csv")
        result.portfolio_pnl.to_csv(specification_root / "portfolio_pnl.csv")
        result.exposure_diagnostics.to_csv(specification_root / "exposure_diagnostics.csv")
        summary_rows.append(
            {
                "specification": label,
                "factors": ",".join(factors),
                "stock_weight": STOCK_WEIGHT,
                "gross_exposure_limit": GROSS_EXPOSURE_LIMIT,
                "transaction_cost_bps": TRANSACTION_COST_BPS,
                "hedge_fraction": HEDGE_FRACTION,
                **metrics,
                "split_adjusted": panels.split_adjusted,
                "dividend_adjusted": panels.dividend_adjusted,
                "corporate_action_adjusted": panels.corporate_action_adjusted,
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_root / "strategy_summary.csv", index=False)
    return summary


def _factor_beta_panels(exposures: pd.DataFrame, factors: list[str]) -> dict[str, pd.DataFrame]:
    return {
        factor: pd.DataFrame(
            {stock: exposures[f"{stock}_{factor}"] for stock in TECH_STOCKS},
            index=exposures.index,
        )
        for factor in factors
    }


if __name__ == "__main__":
    strategy_summary = run()
    print(strategy_summary.to_string(index=False))
    print(f"Saved split-adjusted factor-hedged backtest outputs to {OUTPUT_ROOT}")
