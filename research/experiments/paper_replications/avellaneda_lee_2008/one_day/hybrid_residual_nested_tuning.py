from __future__ import annotations

"""Nested walk-forward tuning for the daily hybrid residual strategy.

Each outer fold selects strategy thresholds on an inner validation window that
sits inside the training window. The selected thresholds are then evaluated once
on the outer test window. This keeps the test fold out of parameter selection.
"""

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_diagnostics import (
    TECH_STOCKS,
    DiagnosticConfig,
    _build_primary_residuals,
    _build_state,
    _concat_dedup,
    _date_index_between,
    _factor_beta_panel,
    _load_cached_or_ingest,
    _mode_counts,
    _prediction_diagnostics,
    _slice_state,
)
from research.tools.backtest import FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator, HybridModeAttributionEvaluator
from research.tools.experiments import TrainTestSlice, WalkForwardPlan, business_days
from research.tools.predictor import ResidualRegimePredictor, build_residual_regime_target
from research.tools.strategy import HybridResidualSignalResult, HybridResidualStrategy
from research.tools.transformer.residual_state import ResidualStateResult

OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "hybrid_residual_nested_tuning"
)
SignalBuilder = Callable[[ResidualStateResult, pd.DataFrame], HybridResidualSignalResult]


@dataclass(frozen=True)
class TuningConfig:
    """Controls inner validation and hyperparameter selection."""

    validation_window_days: int = 126
    objective: str = "sharpe"
    min_validation_active_rate: float = 0.03


@dataclass(frozen=True)
class CandidateSpec:
    """One candidate strategy parameterization for inner-fold tuning."""

    name: str
    family: str
    description: str
    params: dict[str, float | str]
    build_signals: SignalBuilder


def run(output_root: Path = OUTPUT_ROOT) -> pd.DataFrame:
    """Run nested walk-forward tuning and write OOS artifacts."""
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
    _write_config(cfg, tuning_cfg, output_root)

    panels = _load_cached_or_ingest(cfg)
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
    ).build_slices(cfg.start_date, cfg.end_date)
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


def _candidate_grid() -> list[CandidateSpec]:
    candidates: list[CandidateSpec] = []
    for mr_probability in (0.30, 0.35, 0.40):
        for mr_score in (1.25, 1.50, 1.75, 2.00):
            candidates.append(_mean_reversion_candidate(mr_probability, mr_score))

    for trend_probability in (0.60, 0.65, 0.70):
        for trend_score in (1.00, 1.25, 1.50):
            candidates.append(_inverse_trend_candidate(trend_probability, trend_score))

    for mr_probability in (0.30, 0.35):
        for mr_score in (1.50, 1.75):
            for trend_probability in (0.65, 0.70):
                for trend_score in (1.25, 1.50):
                    candidates.append(_combined_candidate(mr_probability, mr_score, trend_probability, trend_score))
    return candidates


def _mean_reversion_candidate(probability: float, score: float) -> CandidateSpec:
    name = f"mr_p{_fmt(probability)}_s{_fmt(score)}"
    return CandidateSpec(
        name=name,
        family="mean_reversion",
        description="Mean-reversion only with tuned probability and displacement thresholds.",
        params={"mr_probability_entry": probability, "mr_entry_score": score},
        build_signals=lambda state, probs, p=probability, s=score: _mean_reversion_signals(state, probs, p, s),
    )


def _inverse_trend_candidate(probability: float, score: float) -> CandidateSpec:
    name = f"invtrend_p{_fmt(probability)}_s{_fmt(score)}"
    return CandidateSpec(
        name=name,
        family="inverse_trend",
        description="Inverse-trend only with tuned probability and trend-score thresholds.",
        params={"trend_probability_entry": probability, "trend_entry_score": score},
        build_signals=lambda state, probs, p=probability, s=score: _inverse_trend_signals(state, probs, p, s),
    )


def _combined_candidate(mr_probability: float, mr_score: float, trend_probability: float, trend_score: float) -> CandidateSpec:
    name = f"mr_p{_fmt(mr_probability)}_s{_fmt(mr_score)}__inv_p{_fmt(trend_probability)}_s{_fmt(trend_score)}"
    return CandidateSpec(
        name=name,
        family="mean_reversion_plus_inverse_trend",
        description="Mean-reversion has priority; otherwise inverse-trend entries are allowed.",
        params={
            "mr_probability_entry": mr_probability,
            "mr_entry_score": mr_score,
            "trend_probability_entry": trend_probability,
            "trend_entry_score": trend_score,
        },
        build_signals=lambda state, probs, mp=mr_probability, ms=mr_score, tp=trend_probability, ts=trend_score: _combine_with_priority(
            _mean_reversion_signals(state, probs, mp, ms),
            _inverse_trend_signals(state, probs, tp, ts),
        ),
    )


_MR_SCORE_SOURCE = "displacement_score"


def _mean_reversion_signals(
    state: ResidualStateResult, probabilities: pd.DataFrame, probability_entry: float, entry_score: float
) -> HybridResidualSignalResult:
    return HybridResidualStrategy(
        trend_probability_entry=0.99,
        trend_probability_exit=0.55,
        mean_reversion_probability_entry=probability_entry,
        mean_reversion_probability_exit=min(0.50, probability_entry + 0.10),
        trend_entry_score=999.0,
        trend_exit_score=998.0,
        mean_reversion_entry_score=entry_score,
        mean_reversion_exit_score=0.50,
        allow_reversal=False,
        mr_score_source=_MR_SCORE_SOURCE,
    ).generate(state, probabilities)


def _inverse_trend_signals(
    state: ResidualStateResult, probabilities: pd.DataFrame, probability_entry: float, entry_score: float
) -> HybridResidualSignalResult:
    trend = HybridResidualStrategy(
        trend_probability_entry=probability_entry,
        trend_probability_exit=max(0.50, probability_entry - 0.10),
        mean_reversion_probability_entry=0.01,
        mean_reversion_probability_exit=0.02,
        trend_entry_score=entry_score,
        trend_exit_score=0.50,
        mean_reversion_entry_score=999.0,
        mean_reversion_exit_score=998.0,
        min_trend_r2=0.10,
        min_relative_volume_for_trend=0.8,
        allow_reversal=False,
        mr_score_source=_MR_SCORE_SOURCE,
    ).generate(state, probabilities)
    return _invert_trend_signals(trend)


def _invert_trend_signals(trend_result: HybridResidualSignalResult) -> HybridResidualSignalResult:
    trend_mask = trend_result.modes.eq("trend")
    signals = (-trend_result.signals).where(trend_mask, 0.0)
    modes = pd.DataFrame("flat", index=trend_result.modes.index, columns=trend_result.modes.columns)
    modes[trend_mask] = "inverse_trend"
    return HybridResidualSignalResult(signals=signals, modes=modes)


def _combine_with_priority(
    primary: HybridResidualSignalResult, secondary: HybridResidualSignalResult
) -> HybridResidualSignalResult:
    primary_active = primary.signals.ne(0.0)
    secondary_active = secondary.signals.ne(0.0) & ~primary_active
    signals = primary.signals.where(primary_active, 0.0)
    signals = signals.where(~secondary_active, secondary.signals)
    modes = pd.DataFrame("flat", index=primary.modes.index, columns=primary.modes.columns)
    modes[primary_active] = primary.modes[primary_active]
    modes[secondary_active] = secondary.modes[secondary_active]
    return HybridResidualSignalResult(signals=signals, modes=modes)


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
        state.features.loc[inner_train_index], target.loc[inner_train_index, TECH_STOCKS]
    )
    validation_probabilities = inner_predictor.predict_proba(state.features.loc[validation_index]).reindex(columns=TECH_STOCKS)
    validation_state = _slice_state(state, validation_index)
    validation_returns = panels.returns.reindex(validation_index).loc[:, TECH_STOCKS + [cfg.factor]]
    validation_factor_betas = {cfg.factor: _factor_beta_panel(exposures, validation_index, cfg.factor)}
    validation_residual_vol = validation_state.residual_volatility.loc[:, TECH_STOCKS]

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
        state.features.loc[train_index], target.loc[train_index, TECH_STOCKS]
    )
    test_probabilities = full_predictor.predict_proba(state.features.loc[test_index]).reindex(columns=TECH_STOCKS)
    test_state = _slice_state(state, test_index)
    signal_result = selected.build_signals(test_state, test_probabilities)
    factor_betas = {cfg.factor: _factor_beta_panel(exposures, test_index, cfg.factor)}
    returns = panels.returns.reindex(test_index).loc[:, TECH_STOCKS + [cfg.factor]]
    test_residual_vol = test_state.residual_volatility.loc[:, TECH_STOCKS]
    backtest = _run_backtest(signal_result, returns, factor_betas, cfg, residual_volatilities=test_residual_vol)
    metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(
        backtest.portfolio_pnl["net_pnl"], positions=backtest.target_weights
    )
    prediction_row = {
        "fold_id": fold.fold_id,
        "selected_candidate": selected.name,
        **_prediction_diagnostics(test_probabilities, target.loc[test_index, TECH_STOCKS], signal_result),
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
        "target": target.loc[test_index, TECH_STOCKS],
        "signals": signal_result.signals,
        "modes": signal_result.modes,
        "weights": backtest.target_weights,
        "asset_pnl": backtest.asset_pnl,
        "portfolio_pnl": backtest.portfolio_pnl,
        "exposure_diagnostics": backtest.exposure_diagnostics,
        "factor_betas": factor_betas[cfg.factor],
    }
    _write_fold_artifacts(output_root / f"fold_{fold.fold_id:03d}", fold_row, validation_rankings, signal_result, backtest)
    return fold_row, selection_row, validation_rankings, prediction_row, fold_parts


def _inner_train_validation_indices(train_index: pd.Index, validation_window_days: int) -> tuple[pd.Index, pd.Index]:
    dates = pd.DatetimeIndex(train_index).date
    days = business_days(min(dates), max(dates))
    if len(days) <= validation_window_days + 20:
        split_date = days[max(1, int(len(days) * 0.75))]
    else:
        split_date = days[-validation_window_days]
    dt_index = pd.DatetimeIndex(train_index)
    inner_train = dt_index[dt_index < pd.Timestamp(split_date)]
    validation = dt_index[dt_index >= pd.Timestamp(split_date)]
    return inner_train, validation


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


def _candidate_score(metrics: dict[str, float], tuning_cfg: TuningConfig) -> float:
    active_rate = metrics.get("active_rate", float("nan"))
    if not np.isfinite(active_rate) or active_rate < tuning_cfg.min_validation_active_rate:
        return float("-inf")
    value = metrics.get(tuning_cfg.objective, float("nan"))
    return float(value) if np.isfinite(value) else float("-inf")


def _select_candidate(rows: list[dict[str, object]], candidates: list[CandidateSpec]) -> CandidateSpec:
    if not rows:
        raise ValueError("No candidate validation rows were produced.")
    selected_name = str(rows[0]["candidate"])
    for candidate in candidates:
        if candidate.name == selected_name:
            return candidate
    raise ValueError(f"Selected candidate {selected_name!r} not found in candidate grid.")


def _selection_row(fold_id: int, selected: CandidateSpec, validation_rankings: list[dict[str, object]]) -> dict[str, object]:
    best_row = validation_rankings[0]
    return {
        "fold_id": fold_id,
        "selected_candidate": selected.name,
        "selected_family": selected.family,
        "description": selected.description,
        **selected.params,
        "validation_selection_score": best_row["selection_score"],
        "validation_cum_return": best_row["cum_return"],
        "validation_sharpe": best_row["sharpe"],
        "validation_max_drawdown": best_row["max_drawdown"],
        "validation_active_rate": best_row["active_rate"],
    }


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


def _write_fold_artifacts(
    fold_root: Path,
    fold_row: dict[str, object],
    validation_rankings: list[dict[str, object]],
    signal_result: HybridResidualSignalResult,
    backtest: FactorHedgedBacktestResult,
) -> None:
    fold_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([fold_row]).to_csv(fold_root / "test_metrics.csv", index=False)
    pd.DataFrame(validation_rankings).to_csv(fold_root / "validation_candidate_rankings.csv", index=False)
    signal_result.signals.to_csv(fold_root / "test_stock_signals.csv")
    signal_result.modes.to_csv(fold_root / "test_modes.csv")
    backtest.target_weights.to_csv(fold_root / "test_target_weights.csv")
    backtest.portfolio_pnl.to_csv(fold_root / "test_portfolio_pnl.csv")


def _write_fold_tables(
    output_root: Path,
    fold_rows: list[dict[str, object]],
    selection_rows: list[dict[str, object]],
    validation_rows: list[dict[str, object]],
    prediction_rows: list[dict[str, object]],
) -> None:
    pd.DataFrame(fold_rows).to_csv(output_root / "fold_metrics.csv", index=False)
    pd.DataFrame(selection_rows).to_csv(output_root / "fold_selected_candidates.csv", index=False)
    pd.DataFrame(validation_rows).to_csv(output_root / "validation_candidate_rankings.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(output_root / "fold_prediction_diagnostics.csv", index=False)


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
        raise ValueError("Nested tuning produced no OOS portfolio pnl.")
    factor_betas = {cfg.factor: stitched["factor_betas"]}
    backtest = FactorHedgedBacktestResult(
        target_weights=stitched["weights"],
        asset_pnl=stitched["asset_pnl"],
        portfolio_pnl=stitched["portfolio_pnl"],
        exposure_diagnostics=stitched["exposure_diagnostics"],
    )
    attribution = HybridModeAttributionEvaluator(modes=("mean_reversion", "inverse_trend", "flat")).evaluate(
        backtest, stitched["modes"], factor_betas
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
                "experiment": "hybrid_residual_nested_tuning",
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


def _candidate_frame(candidates: list[CandidateSpec]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"candidate": c.name, "family": c.family, "description": c.description, **c.params}
            for c in candidates
        ]
    )


def _write_config(cfg: DiagnosticConfig, tuning_cfg: TuningConfig, output_root: Path) -> None:
    pd.DataFrame([{**asdict(cfg), **asdict(tuning_cfg)}]).to_csv(output_root / "config.csv", index=False)


def _write_summary_txt(
    summary: pd.DataFrame,
    mode_summary: pd.DataFrame,
    selection_counts: pd.DataFrame,
    family_counts: pd.DataFrame,
    output_root: Path,
) -> None:
    lines = [
        "Hybrid residual nested walk-forward tuning",
        "",
        "No-leakage design: candidates are selected on each fold's inner validation window, then evaluated once on the outer test window.",
        "",
        "Overall summary:",
        summary.to_string(index=False),
        "",
        "Selected candidate counts:",
        selection_counts.to_string(index=False),
        "",
        "Selected family counts:",
        family_counts.to_string(index=False),
        "",
        "Mode attribution:",
        mode_summary.to_string(index=False),
    ]
    (output_root / "summary.txt").write_text("\n".join(lines), encoding="utf-8")


def _fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", "")


if __name__ == "__main__":
    result = run()
    print(result.to_string(index=False))
    print(f"Saved nested tuning results to {OUTPUT_ROOT}")
