from __future__ import annotations

"""Multi-sector daily hybrid residual strategy with nested walk-forward tuning.

Replicates the structure of ``hybrid_residual_nested_tuning`` but uses the
25-stock, five-sector universe from ``sector_etf.config`` with per-stock
sector-ETF residualization and per-sector hedging. The intent is to test
whether the Sharpe gain from cross-sector diversification compounds with the
per-stock residual-vol-targeted sizing already enabled in the engine.
"""

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_diagnostics import (
    DiagnosticConfig,
    _build_state,
    _concat_dedup,
    _date_index_between,
    _mode_counts,
    _prediction_diagnostics,
    _slice_state,
)
from research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_nested_tuning import (
    CandidateSpec,
    TuningConfig,
    _candidate_frame,
    _candidate_grid,
    _candidate_score,
    _inner_train_validation_indices,
    _select_candidate,
    _selection_row,
    _write_fold_artifacts,
    _write_fold_tables,
    _write_summary_txt,
)
from research.experiments.paper_replications.avellaneda_lee_2008.one_day.sector_etf.config import (
    FACTOR_ETFS,
    MARKET_FACTOR,
    SECTOR_STOCKS,
    STOCKS,
    STOCK_TO_ETF,
    TRADING_START_DATE,
)

DUAL_FACTOR_SECTORS: frozenset[str] = frozenset({"XLF", "XLE"})
STOCK_FACTORS: dict[str, tuple[str, ...]] = {
    stock: (MARKET_FACTOR, etf) if etf in DUAL_FACTOR_SECTORS else (etf,)
    for stock, etf in STOCK_TO_ETF.items()
}
ALL_FACTORS: tuple[str, ...] = tuple(dict.fromkeys(f for fs in STOCK_FACTORS.values() for f in fs))
from research.experiments.paper_replications.avellaneda_lee_2008.one_day.sector_etf.ingest_theta_eod_data import (
    load_or_fetch_panels,
)
from research.tools.backtest import FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator, HybridModeAttributionEvaluator
from research.tools.experiments import TrainTestSlice, WalkForwardPlan
from research.tools.predictor import ResidualRegimePredictor, build_residual_regime_target
from research.tools.strategy import HybridResidualSignalResult
from research.tools.transformer.residual_state import ResidualStateResult
from research.tools.transformer.residualization import (
    FactorSpec,
    RollingFactorResidualizationModel,
    RollingOLSExposureEstimator,
)

OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "multi_sector_hybrid_nested_tuning"
)


def run(output_root: Path = OUTPUT_ROOT) -> pd.DataFrame:
    """Run nested walk-forward tuning over the 25-stock five-sector universe."""
    cfg = DiagnosticConfig(
        residual_volatility_target=0.015,
        portfolio_vol_target=None,
        portfolio_vol_lookback=20,
        max_position_multiplier=3.0,
        max_portfolio_scale=15.0,
        enable_ou_score=False,
    )
    tuning_cfg = TuningConfig()
    output_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{**asdict(cfg), **asdict(tuning_cfg)}]).to_csv(output_root / "config.csv", index=False)
    pd.DataFrame(
        [{"sector_etf": factor, "stocks": ",".join(stocks)} for factor, stocks in SECTOR_STOCKS.items()]
    ).to_csv(output_root / "universe.csv", index=False)

    panels = load_or_fetch_panels()
    residuals, exposures = _build_primary_residuals(panels, cfg)
    state = _build_state(panels, residuals, cfg)
    target = build_residual_regime_target(
        residual_returns=residuals,
        trend_score=state.trend_score,
        displacement_score=state.displacement_score,
        min_abs_score=cfg.min_target_score,
    )
    slices = WalkForwardPlan(
        train_window_days=cfg.train_window_days,
        test_window_days=cfg.test_window_days,
        step_days=cfg.step_days,
        anchored=False,
        retrain_every_n_folds=1,
    ).build_slices(TRADING_START_DATE, cfg.end_date)
    candidates = _candidate_grid()
    _candidate_frame(candidates).to_csv(output_root / "candidate_grid.csv", index=False)

    parts = _empty_parts()
    fold_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    validation_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []

    for fold in slices:
        fold_result = _run_outer_fold(
            fold=fold,
            panels=panels,
            residuals=residuals,
            exposures=exposures,
            state=state,
            target=target,
            candidates=candidates,
            cfg=cfg,
            tuning_cfg=tuning_cfg,
            output_root=output_root,
        )
        if fold_result is None:
            continue
        fold_row, selection_row, validation_rankings, prediction_row, fold_parts = fold_result
        fold_rows.append(fold_row)
        selection_rows.append(selection_row)
        validation_rows.extend(validation_rankings)
        prediction_rows.append(prediction_row)
        _append_parts(parts, fold_parts)

    _write_fold_tables(output_root, fold_rows, selection_rows, validation_rows, prediction_rows)
    summary = _write_oos_outputs(output_root, parts, cfg, fold_rows, selection_rows, tuning_cfg)
    return summary


def _build_primary_residuals(panels, cfg: DiagnosticConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = FactorSpec({stock: list(STOCK_FACTORS[stock]) for stock in STOCKS})
    model = RollingFactorResidualizationModel(
        spec=spec,
        estimator=RollingOLSExposureEstimator(
            window=cfg.residual_window_days,
            min_obs=cfg.residual_window_days,
            fit_intercept=True,
        ),
    )
    residuals = model.fit_transform(panels.returns.sort_index())
    exposures = pd.concat(
        [path.add_prefix(f"{stock}_") for stock, path in model.exposure_paths.items()], axis=1
    )
    return residuals, exposures


def _factor_beta_panels(exposures: pd.DataFrame, index: pd.Index) -> dict[str, pd.DataFrame]:
    panels: dict[str, pd.DataFrame] = {}
    zero = pd.Series(0.0, index=exposures.index)
    for factor in ALL_FACTORS:
        cols: dict[str, pd.Series] = {}
        for stock in STOCKS:
            cols[stock] = exposures[f"{stock}_{factor}"] if factor in STOCK_FACTORS[stock] else zero
        panel = pd.DataFrame(cols).reindex(index)
        panels[factor] = panel.fillna(0.0)
    return panels


def _run_outer_fold(
    fold: TrainTestSlice,
    panels,
    residuals: pd.DataFrame,
    exposures: pd.DataFrame,
    state: ResidualStateResult,
    target: pd.DataFrame,
    candidates: list[CandidateSpec],
    cfg: DiagnosticConfig,
    tuning_cfg: TuningConfig,
    output_root: Path,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object], dict[str, pd.DataFrame]] | None:
    train_index = _date_index_between(residuals.index, fold.train_start, fold.train_end)
    test_index = _date_index_between(residuals.index, fold.test_start, fold.test_end)
    if len(train_index) == 0 or len(test_index) == 0:
        return None

    inner_train_index, validation_index = _inner_train_validation_indices(train_index, tuning_cfg.validation_window_days)
    if len(inner_train_index) == 0 or len(validation_index) == 0:
        return None

    inner_predictor = ResidualRegimePredictor(min_obs=cfg.min_regime_obs).fit(
        state.features.loc[inner_train_index], target.loc[inner_train_index, STOCKS]
    )
    validation_probabilities = inner_predictor.predict_proba(state.features.loc[validation_index]).reindex(columns=STOCKS)
    validation_state = _slice_state(state, validation_index)
    validation_returns = panels.returns.reindex(validation_index).loc[:, STOCKS + FACTOR_ETFS]
    validation_factor_betas = _factor_beta_panels(exposures, validation_index)
    validation_residual_vol = validation_state.residual_volatility.loc[:, STOCKS]

    validation_rankings = _rank_candidates(
        candidates=candidates,
        state=validation_state,
        probabilities=validation_probabilities,
        returns=validation_returns,
        factor_betas=validation_factor_betas,
        residual_volatilities=validation_residual_vol,
        cfg=cfg,
        tuning_cfg=tuning_cfg,
        fold_id=fold.fold_id,
    )
    selected = _select_candidate(validation_rankings, candidates)

    full_predictor = ResidualRegimePredictor(min_obs=cfg.min_regime_obs).fit(
        state.features.loc[train_index], target.loc[train_index, STOCKS]
    )
    test_probabilities = full_predictor.predict_proba(state.features.loc[test_index]).reindex(columns=STOCKS)
    test_state = _slice_state(state, test_index)
    signal_result = selected.build_signals(test_state, test_probabilities)
    factor_betas = _factor_beta_panels(exposures, test_index)
    returns = panels.returns.reindex(test_index).loc[:, STOCKS + FACTOR_ETFS]
    test_residual_vol = test_state.residual_volatility.loc[:, STOCKS]
    backtest = _run_backtest(signal_result, returns, factor_betas, cfg, residual_volatilities=test_residual_vol)
    metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(
        backtest.portfolio_pnl["net_pnl"], positions=backtest.target_weights
    )
    prediction_row = {
        "fold_id": fold.fold_id,
        "selected_candidate": selected.name,
        **_prediction_diagnostics(test_probabilities, target.loc[test_index, STOCKS], signal_result),
    }
    fold_row = {
        "fold_id": fold.fold_id,
        "train_start": fold.train_start.isoformat(),
        "train_end": fold.train_end.isoformat(),
        "inner_train_start": pd.Timestamp(inner_train_index[0]).date().isoformat(),
        "inner_train_end": pd.Timestamp(inner_train_index[-1]).date().isoformat(),
        "validation_start": pd.Timestamp(validation_index[0]).date().isoformat(),
        "validation_end": pd.Timestamp(validation_index[-1]).date().isoformat(),
        "test_start": fold.test_start.isoformat(),
        "test_end": fold.test_end.isoformat(),
        "selected_candidate": selected.name,
        "selected_family": selected.family,
        **selected.params,
        **metrics,
        **_mode_counts(signal_result.modes),
    }
    selection_row = _selection_row(fold.fold_id, selected, validation_rankings)
    fold_parts = {
        "probabilities": test_probabilities,
        "target": target.loc[test_index, STOCKS],
        "signals": signal_result.signals,
        "modes": signal_result.modes,
        "weights": backtest.target_weights,
        "asset_pnl": backtest.asset_pnl,
        "portfolio_pnl": backtest.portfolio_pnl,
        "exposure_diagnostics": backtest.exposure_diagnostics,
        "factor_betas": pd.concat(
            [betas.add_prefix(f"{factor}__") for factor, betas in factor_betas.items()], axis=1
        ),
    }
    _write_fold_artifacts(output_root / f"fold_{fold.fold_id:03d}", fold_row, validation_rankings, signal_result, backtest)
    return fold_row, selection_row, validation_rankings, prediction_row, fold_parts


def _rank_candidates(
    candidates: list[CandidateSpec],
    state: ResidualStateResult,
    probabilities: pd.DataFrame,
    returns: pd.DataFrame,
    factor_betas: dict[str, pd.DataFrame],
    residual_volatilities: pd.DataFrame,
    cfg: DiagnosticConfig,
    tuning_cfg: TuningConfig,
    fold_id: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        signal_result = candidate.build_signals(state, probabilities)
        backtest = _run_backtest(signal_result, returns, factor_betas, cfg, residual_volatilities=residual_volatilities)
        metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(
            backtest.portfolio_pnl["net_pnl"], positions=backtest.target_weights
        )
        score = _candidate_score(metrics, tuning_cfg)
        rows.append(
            {
                "fold_id": fold_id,
                "candidate": candidate.name,
                "family": candidate.family,
                "selection_score": score,
                **candidate.params,
                **metrics,
                **_mode_counts(signal_result.modes),
            }
        )
    rows.sort(key=lambda row: float(row["selection_score"]), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["validation_rank"] = rank
    return rows


def _run_backtest(
    signal_result: HybridResidualSignalResult,
    returns: pd.DataFrame,
    factor_betas: dict[str, pd.DataFrame],
    cfg: DiagnosticConfig,
    residual_volatilities: pd.DataFrame | None = None,
) -> FactorHedgedBacktestResult:
    engine = FactorHedgedDailyBacktestEngine(
        stock_weight=cfg.stock_weight,
        gross_exposure_limit=cfg.gross_exposure_limit,
        transaction_cost_bps=cfg.transaction_cost_bps,
        hedge_fraction=cfg.hedge_fraction,
        residual_volatility_target=cfg.residual_volatility_target,
        max_position_multiplier=cfg.max_position_multiplier,
        portfolio_vol_target=cfg.portfolio_vol_target,
        portfolio_vol_lookback=cfg.portfolio_vol_lookback,
        max_portfolio_scale=cfg.max_portfolio_scale,
    )
    return engine.run(
        stock_signals=signal_result.signals,
        returns=returns,
        factor_betas=factor_betas,
        residual_volatilities=residual_volatilities,
    )


def _empty_parts() -> dict[str, list[pd.DataFrame]]:
    return {
        "probabilities": [],
        "target": [],
        "signals": [],
        "modes": [],
        "weights": [],
        "asset_pnl": [],
        "portfolio_pnl": [],
        "exposure_diagnostics": [],
        "factor_betas": [],
    }


def _append_parts(parts: dict[str, list[pd.DataFrame]], fold_parts: dict[str, pd.DataFrame]) -> None:
    for key, value in fold_parts.items():
        parts[key].append(value)


def _write_oos_outputs(
    output_root: Path,
    parts: dict[str, list[pd.DataFrame]],
    cfg: DiagnosticConfig,
    fold_rows: list[dict[str, object]],
    selection_rows: list[dict[str, object]],
    tuning_cfg: TuningConfig,
) -> pd.DataFrame:
    stitched = {key: _concat_dedup(value) for key, value in parts.items()}
    if stitched["portfolio_pnl"].empty:
        raise ValueError("Multi-sector nested tuning produced no OOS portfolio pnl.")
    backtest = FactorHedgedBacktestResult(
        target_weights=stitched["weights"],
        asset_pnl=stitched["asset_pnl"],
        portfolio_pnl=stitched["portfolio_pnl"],
        exposure_diagnostics=stitched["exposure_diagnostics"],
    )
    factor_betas_stitched = stitched["factor_betas"]
    factor_betas_dict = {
        factor: factor_betas_stitched[
            [col for col in factor_betas_stitched.columns if col.startswith(f"{factor}__")]
        ].rename(columns=lambda c: c.split("__", 1)[1])
        for factor in SECTOR_STOCKS
    }
    attribution = HybridModeAttributionEvaluator(modes=("mean_reversion", "inverse_trend", "flat")).evaluate(
        backtest, stitched["modes"], factor_betas_dict
    )
    metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(
        backtest.portfolio_pnl["net_pnl"], positions=backtest.target_weights
    )
    selection_counts = pd.DataFrame(selection_rows)["selected_candidate"].value_counts().rename_axis("candidate").reset_index(name="selected_folds")
    family_counts = pd.DataFrame(selection_rows)["selected_family"].value_counts().rename_axis("family").reset_index(name="selected_folds")

    for key, value in stitched.items():
        value.to_csv(output_root / f"oos_{key}.csv")
    attribution.summary.to_csv(output_root / "mode_attribution_summary.csv", index=False)
    attribution.stock_summary.to_csv(output_root / "stock_mode_summary.csv", index=False)
    selection_counts.to_csv(output_root / "selected_candidate_counts.csv", index=False)
    family_counts.to_csv(output_root / "selected_family_counts.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "experiment": "multi_sector_hybrid_nested_tuning",
                "num_folds": len(fold_rows),
                "selection_objective": tuning_cfg.objective,
                "min_validation_active_rate": tuning_cfg.min_validation_active_rate,
                **metrics,
            }
        ]
    )
    summary.to_csv(output_root / "summary.csv", index=False)
    _write_summary_txt(summary, attribution.summary, selection_counts, family_counts, output_root)
    return summary


if __name__ == "__main__":
    result = run()
    print(result.to_string(index=False))
    print(f"Saved multi-sector nested tuning results to {OUTPUT_ROOT}")
