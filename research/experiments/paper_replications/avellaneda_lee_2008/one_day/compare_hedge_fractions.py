from __future__ import annotations

"""Compare execution hedge fractions for the same daily OU residual signal."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.tools.backtest import FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.processing import DailyEodPanels
from research.tools.strategy import OUSScoreStrategy
from research.tools.transformer.mean_reversion import OUEstimator, RollingOUScoreModel

from .backtest_s_score_strategy import GROSS_EXPOSURE_LIMIT, STOCK_WEIGHT, TRANSACTION_COST_BPS
from .estimate_ou_scores import MAX_MEAN_REVERSION_DAYS, SCORE_START_DATE
from .ingest_theta_eod_data import (
    END_DATE,
    FACTOR_ETFS,
    START_DATE,
    TECH_STOCKS,
    load_cached_panels,
    run as ingest_eod,
)
from .rolling_etf_residualization import ESTIMATION_WINDOW, FACTOR_SPECS, build_residual_paths

HEDGE_FRACTIONS = (0.0, 0.25, 0.50, 0.75, 1.0)
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "hedge_fraction_comparison"
)


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    trading_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
    refresh_data: bool = False,
) -> pd.DataFrame:
    """Compare partial factor hedging, optionally refreshing raw ThetaData first."""
    panels = (
        ingest_eod(start_date=start_date, end_date=end_date)
        if refresh_data
        else load_cached_panels(start_date=start_date, end_date=end_date)
    )
    return build_outputs(panels, trading_start_date=trading_start_date, output_root=output_root)


def build_outputs(
    panels: DailyEodPanels,
    trading_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Evaluate identical residual signals under alternative hedge fractions."""
    strategy = OUSScoreStrategy()
    scorer = RollingOUScoreModel(
        window=ESTIMATION_WINDOW,
        estimator=OUEstimator(max_mean_reversion_days=MAX_MEAN_REVERSION_DAYS),
    )
    evaluator = BasicStrategyEvaluator(annualization_factor=252)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []
    start_timestamp = pd.Timestamp(trading_start_date)

    for label, (residuals, exposures) in build_residual_paths(panels).items():
        factors = FACTOR_SPECS[label]
        ou_result = scorer.transform(residuals)
        scores = ou_result.scores.loc[start_timestamp:, TECH_STOCKS]
        eligibility = ou_result.eligibility.loc[start_timestamp:, TECH_STOCKS]
        signals = strategy.generate(scores, eligibility=eligibility)
        betas = _factor_beta_panels(exposures.reindex(signals.index), factors)
        returns = panels.returns.reindex(signals.index).loc[:, TECH_STOCKS + factors]
        reference_returns = panels.returns.reindex(signals.index).loc[:, FACTOR_ETFS]
        specification_root = output_root / label
        specification_root.mkdir(parents=True, exist_ok=True)
        signals.to_csv(specification_root / "stock_signals.csv")

        for hedge_fraction in HEDGE_FRACTIONS:
            result = _run_backtest(signals, returns, betas, hedge_fraction)
            summary_rows.append(
                _summary_row(
                    label, factors, hedge_fraction, result.portfolio_pnl, result.target_weights,
                    result.exposure_diagnostics, reference_returns, evaluator, panels
                )
            )
            _write_result(result, specification_root / f"hedge_fraction={hedge_fraction:.2f}")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_root / "hedge_fraction_comparison.csv", index=False)
    return summary


def _run_backtest(
    signals: pd.DataFrame,
    returns: pd.DataFrame,
    betas: dict[str, pd.DataFrame],
    hedge_fraction: float,
) -> FactorHedgedBacktestResult:
    engine = FactorHedgedDailyBacktestEngine(
        stock_weight=STOCK_WEIGHT,
        gross_exposure_limit=GROSS_EXPOSURE_LIMIT,
        transaction_cost_bps=TRANSACTION_COST_BPS,
        hedge_fraction=hedge_fraction,
    )
    return engine.run(stock_signals=signals, returns=returns, factor_betas=betas)


def _summary_row(
    label: str,
    factors: list[str],
    hedge_fraction: float,
    pnl: pd.DataFrame,
    positions: pd.DataFrame,
    diagnostics: pd.DataFrame,
    reference_returns: pd.DataFrame,
    evaluator: BasicStrategyEvaluator,
    panels: DailyEodPanels,
) -> dict[str, object]:
    gross = evaluator.evaluate(pnl["gross_pnl"], positions=positions)
    net = evaluator.evaluate(pnl["net_pnl"], positions=positions)
    row: dict[str, object] = {
        "specification": label,
        "factors": ",".join(factors),
        "hedge_fraction": hedge_fraction,
        "stock_weight": STOCK_WEIGHT,
        "gross_exposure_limit": GROSS_EXPOSURE_LIMIT,
        "transaction_cost_bps": TRANSACTION_COST_BPS,
        "gross_cum_return": gross["cum_return"],
        "net_cum_return": net["cum_return"],
        "total_transaction_cost": float(pnl["transaction_cost"].sum()),
        "net_sharpe": net["sharpe"],
        "net_max_drawdown": net["max_drawdown"],
        "turnover": net["turnover"],
        "avg_gross_exposure": net["avg_gross_exposure"],
        "active_rate": net["active_rate"],
        "pnl_corr_xlk": pnl["net_pnl"].corr(reference_returns["XLK"]),
        "pnl_corr_spy": pnl["net_pnl"].corr(reference_returns["SPY"]),
        "split_adjusted": panels.split_adjusted,
        "dividend_adjusted": panels.dividend_adjusted,
        "corporate_action_adjusted": panels.corporate_action_adjusted,
    }
    for factor in FACTOR_ETFS:
        column = f"net_{factor}_exposure"
        row[f"avg_abs_remaining_{factor.lower()}_exposure"] = (
            float(diagnostics[column].abs().mean()) if column in diagnostics else float("nan")
        )
    return row


def _factor_beta_panels(exposures: pd.DataFrame, factors: list[str]) -> dict[str, pd.DataFrame]:
    return {
        factor: pd.DataFrame(
            {stock: exposures[f"{stock}_{factor}"] for stock in TECH_STOCKS},
            index=exposures.index,
        )
        for factor in factors
    }


def _write_result(result: FactorHedgedBacktestResult, output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    result.target_weights.to_csv(output_root / "target_weights.csv")
    result.asset_pnl.to_csv(output_root / "asset_pnl.csv")
    result.portfolio_pnl.to_csv(output_root / "portfolio_pnl.csv")
    result.exposure_diagnostics.to_csv(output_root / "exposure_diagnostics.csv")


if __name__ == "__main__":
    comparison = run()
    print(comparison.to_string(index=False))
    print(f"Saved hedge-fraction comparison outputs to {OUTPUT_ROOT}")
