from __future__ import annotations

"""Run full-data hybrid residual diagnostics for the daily ETF replication."""

import argparse
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from research.experiments.paper_replications.avellaneda_lee_2008.one_day.configured_splits import (
    RAW_CLOSE_SPLIT_EVENTS,
)
from research.experiments.paper_replications.avellaneda_lee_2008.one_day.ingest_theta_eod_data import (
    END_DATE,
    FACTOR_ETFS,
    OUTPUT_ROOT as INGESTION_CACHE_ROOT,
    START_DATE,
    TECH_STOCKS,
    run as ingest_eod,
)
from research.tools.backtest import FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.data import (
    CachedPanelSource,
    LayeredPanelSource,
    PanelRequest,
    ThetaPanelSource,
    UniverseSpec,
)
from research.tools.evaluation import BasicStrategyEvaluator, HybridModeAttributionEvaluator
from research.tools.experiments import TrainTestSlice, WalkForwardPlan
from research.tools.predictor import ResidualRegimePredictor, build_residual_regime_target
from research.tools.processing import DailyEodPanels
from research.tools.strategy import HybridResidualStrategy, HybridResidualSignalResult
from research.tools.transformer.mean_reversion import OUEstimator
from research.tools.transformer.residual_state import ResidualStateResult, ResidualStateTransformer
from research.tools.transformer.residualization import FactorSpec, RollingFactorResidualizationModel, RollingOLSExposureEstimator

OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "hybrid_residual_diagnostics"
)
FACTOR = "XLK"
RESIDUAL_WINDOW = 60
STATE_LEVEL_WINDOW = 60
STATE_TREND_WINDOW = 20
STATE_VOL_WINDOW = 20
STATE_VOLUME_WINDOW = 60
TRAIN_WINDOW_DAYS = 504
TEST_WINDOW_DAYS = 63
STEP_DAYS = 63
MIN_REGIME_OBS = 150
MIN_TARGET_SCORE = 0.25
STOCK_WEIGHT = 0.05
TRANSACTION_COST_BPS = 5.0
GROSS_EXPOSURE_LIMIT = 2.0
HEDGE_FRACTION = 1.0
RESIDUAL_VOLATILITY_TARGET: float | None = None
MAX_POSITION_MULTIPLIER = 3.0
PORTFOLIO_VOL_TARGET: float | None = None
PORTFOLIO_VOL_LOOKBACK = 20
MAX_PORTFOLIO_SCALE = 15.0
ENABLE_OU_SCORE = False
OU_MAX_MEAN_REVERSION_DAYS = 30.0


@dataclass(frozen=True)
class DiagnosticConfig:
    start_date: date = START_DATE
    end_date: date = END_DATE
    factor: str = FACTOR
    residual_window_days: int = RESIDUAL_WINDOW
    state_level_window: int = STATE_LEVEL_WINDOW
    state_trend_window: int = STATE_TREND_WINDOW
    state_volatility_window: int = STATE_VOL_WINDOW
    state_volume_window: int = STATE_VOLUME_WINDOW
    train_window_days: int = TRAIN_WINDOW_DAYS
    test_window_days: int = TEST_WINDOW_DAYS
    step_days: int = STEP_DAYS
    min_regime_obs: int = MIN_REGIME_OBS
    min_target_score: float = MIN_TARGET_SCORE
    stock_weight: float = STOCK_WEIGHT
    transaction_cost_bps: float = TRANSACTION_COST_BPS
    gross_exposure_limit: float = GROSS_EXPOSURE_LIMIT
    hedge_fraction: float = HEDGE_FRACTION
    residual_volatility_target: float | None = RESIDUAL_VOLATILITY_TARGET
    max_position_multiplier: float = MAX_POSITION_MULTIPLIER
    portfolio_vol_target: float | None = PORTFOLIO_VOL_TARGET
    portfolio_vol_lookback: int = PORTFOLIO_VOL_LOOKBACK
    max_portfolio_scale: float = MAX_PORTFOLIO_SCALE
    enable_ou_score: bool = ENABLE_OU_SCORE
    ou_max_mean_reversion_days: float = OU_MAX_MEAN_REVERSION_DAYS


def run(refresh_data: bool = False, output_root: Path = OUTPUT_ROOT) -> pd.DataFrame:
    """Run the full diagnostic experiment and write artifacts to disk."""
    cfg = DiagnosticConfig()
    output_root.mkdir(parents=True, exist_ok=True)
    _write_config(cfg, output_root)

    panels = ingest_eod(start_date=cfg.start_date, end_date=cfg.end_date) if refresh_data else _load_cached_or_ingest(cfg)
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

    _write_static_diagnostics(panels, residuals, exposures, state, target, output_root)
    stitched = _run_walk_forward(panels, residuals, exposures, state, target, slices, cfg, output_root)
    summary = _write_oos_diagnostics(stitched, cfg, output_root)
    return summary


def _default_universe() -> UniverseSpec:
    return UniverseSpec(
        stocks=tuple(TECH_STOCKS),
        factor_etfs=tuple(FACTOR_ETFS),
        split_events=tuple(RAW_CLOSE_SPLIT_EVENTS),
    )


def _load_cached_or_ingest(cfg: DiagnosticConfig) -> DailyEodPanels:
    """Return panels via the layered DataSource: cache first, ThetaData fallback.

    The function name is preserved so existing callers (nested-tuning,
    multi-sector) keep working unchanged, but the implementation now flows
    through ``research.tools.data`` so any caller can swap in a custom
    ``DataSource`` by replacing this one call.
    """
    request = PanelRequest(
        universe=_default_universe(),
        start_date=cfg.start_date,
        end_date=cfg.end_date,
    )
    source = LayeredPanelSource(
        [
            CachedPanelSource(INGESTION_CACHE_ROOT),
            ThetaPanelSource(cache_root=INGESTION_CACHE_ROOT),
        ]
    )
    return source.get_panels(request)


def _build_primary_residuals(panels: DailyEodPanels, cfg: DiagnosticConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    model = RollingFactorResidualizationModel(
        spec=FactorSpec({stock: [cfg.factor] for stock in TECH_STOCKS}),
        estimator=RollingOLSExposureEstimator(window=cfg.residual_window_days, min_obs=cfg.residual_window_days, fit_intercept=True),
    )
    residuals = model.fit_transform(panels.returns.sort_index())
    exposures = pd.concat(
        [path.add_prefix(f"{stock}_") for stock, path in model.exposure_paths.items()], axis=1
    )
    return residuals, exposures


def _build_state(panels: DailyEodPanels, residuals: pd.DataFrame, cfg: DiagnosticConfig) -> ResidualStateResult:
    ou_estimator = (
        OUEstimator(max_mean_reversion_days=cfg.ou_max_mean_reversion_days) if cfg.enable_ou_score else None
    )
    return ResidualStateTransformer(
        level_window=cfg.state_level_window,
        trend_window=cfg.state_trend_window,
        volatility_window=cfg.state_volatility_window,
        volume_window=cfg.state_volume_window,
        ou_estimator=ou_estimator,
    ).transform(residuals, volumes=panels.volumes, dollar_volumes=panels.dollar_volumes)


def _run_walk_forward(
    panels: DailyEodPanels,
    residuals: pd.DataFrame,
    exposures: pd.DataFrame,
    state: ResidualStateResult,
    target: pd.DataFrame,
    slices: list[TrainTestSlice],
    cfg: DiagnosticConfig,
    output_root: Path,
) -> dict[str, object]:
    fold_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    parts: dict[str, list[pd.DataFrame]] = {
        "probabilities": [],
        "target": [],
        "signals": [],
        "modes": [],
        "weights": [],
        "asset_pnl": [],
        "portfolio_pnl": [],
        "exposure_diagnostics": [],
        "factor_betas": [],
        "attribution_daily": [],
    }

    for fold in slices:
        fold_root = output_root / f"fold_{fold.fold_id:03d}"
        fold_root.mkdir(parents=True, exist_ok=True)
        train_index = _date_index_between(residuals.index, fold.train_start, fold.train_end)
        test_index = _date_index_between(residuals.index, fold.test_start, fold.test_end)
        if len(train_index) == 0 or len(test_index) == 0:
            continue

        predictor = ResidualRegimePredictor(min_obs=cfg.min_regime_obs).fit(
            state.features.loc[train_index], target.loc[train_index, TECH_STOCKS]
        )
        probabilities = predictor.predict_proba(state.features.loc[test_index]).reindex(columns=TECH_STOCKS)
        test_state = _slice_state(state, test_index)
        signal_result = HybridResidualStrategy(min_trend_r2=0.10, min_relative_volume_for_trend=0.8).generate(
            test_state, probabilities
        )
        factor_betas = {cfg.factor: _factor_beta_panel(exposures, test_index, cfg.factor)}
        returns = panels.returns.reindex(test_index).loc[:, TECH_STOCKS + [cfg.factor]]
        test_residual_vol = test_state.residual_volatility.loc[:, TECH_STOCKS]
        backtest = FactorHedgedDailyBacktestEngine(
            stock_weight=cfg.stock_weight,
            gross_exposure_limit=cfg.gross_exposure_limit,
            transaction_cost_bps=cfg.transaction_cost_bps,
            hedge_fraction=cfg.hedge_fraction,
            residual_volatility_target=cfg.residual_volatility_target,
            max_position_multiplier=cfg.max_position_multiplier,
            portfolio_vol_target=cfg.portfolio_vol_target,
            portfolio_vol_lookback=cfg.portfolio_vol_lookback,
            max_portfolio_scale=cfg.max_portfolio_scale,
        ).run(
            stock_signals=signal_result.signals,
            returns=returns,
            factor_betas=factor_betas,
            residual_volatilities=test_residual_vol,
        )
        attribution = HybridModeAttributionEvaluator().evaluate(backtest, signal_result.modes, factor_betas)
        fold_metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(
            backtest.portfolio_pnl["net_pnl"], positions=backtest.target_weights
        )
        pred_diag = _prediction_diagnostics(probabilities, target.loc[test_index, TECH_STOCKS], signal_result)
        fold_row = {
            "fold_id": fold.fold_id,
            "train_start": fold.train_start.isoformat(),
            "train_end": fold.train_end.isoformat(),
            "test_start": fold.test_start.isoformat(),
            "test_end": fold.test_end.isoformat(),
            "fitted_symbol_count": len(predictor.fitted_symbols),
            **fold_metrics,
            **_mode_counts(signal_result.modes),
        }
        fold_rows.append(fold_row)
        prediction_rows.append({"fold_id": fold.fold_id, **pred_diag})

        _write_fold_artifacts(fold_root, probabilities, target.loc[test_index, TECH_STOCKS], signal_result, backtest, attribution, fold_row, pred_diag)
        parts["probabilities"].append(probabilities)
        parts["target"].append(target.loc[test_index, TECH_STOCKS])
        parts["signals"].append(signal_result.signals)
        parts["modes"].append(signal_result.modes)
        parts["weights"].append(backtest.target_weights)
        parts["asset_pnl"].append(backtest.asset_pnl)
        parts["portfolio_pnl"].append(backtest.portfolio_pnl)
        parts["exposure_diagnostics"].append(backtest.exposure_diagnostics)
        parts["factor_betas"].append(factor_betas[cfg.factor])
        parts["attribution_daily"].append(attribution.daily_pnl)

    pd.DataFrame(fold_rows).to_csv(output_root / "fold_metrics.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(output_root / "fold_prediction_diagnostics.csv", index=False)
    return {name: _concat_dedup(frames) for name, frames in parts.items()}


def _write_oos_diagnostics(stitched: dict[str, object], cfg: DiagnosticConfig, output_root: Path) -> pd.DataFrame:
    probabilities = stitched["probabilities"]
    target = stitched["target"]
    signals = stitched["signals"]
    modes = stitched["modes"]
    weights = stitched["weights"]
    asset_pnl = stitched["asset_pnl"]
    portfolio_pnl = stitched["portfolio_pnl"]
    exposure_diagnostics = stitched["exposure_diagnostics"]
    factor_betas = {cfg.factor: stitched["factor_betas"]}
    backtest = FactorHedgedBacktestResult(weights, asset_pnl, portfolio_pnl, exposure_diagnostics)
    attribution = HybridModeAttributionEvaluator().evaluate(backtest, modes, factor_betas)

    probabilities.to_csv(output_root / "oos_regime_probabilities.csv")
    target.to_csv(output_root / "oos_regime_target.csv")
    signals.to_csv(output_root / "oos_stock_signals.csv")
    modes.to_csv(output_root / "oos_modes.csv")
    weights.to_csv(output_root / "oos_target_weights.csv")
    asset_pnl.to_csv(output_root / "oos_asset_pnl.csv")
    portfolio_pnl.to_csv(output_root / "oos_portfolio_pnl.csv")
    exposure_diagnostics.to_csv(output_root / "oos_exposure_diagnostics.csv")
    attribution.daily_pnl.to_csv(output_root / "mode_attribution_daily_pnl.csv")
    attribution.summary.to_csv(output_root / "mode_attribution_summary.csv", index=False)
    attribution.stock_summary.to_csv(output_root / "stock_mode_summary.csv", index=False)
    _prediction_diagnostics_by_symbol(probabilities, target).to_csv(output_root / "oos_prediction_diagnostics_by_symbol.csv", index=False)
    _signal_diagnostics_by_symbol(signals, modes).to_csv(output_root / "oos_signal_diagnostics_by_symbol.csv", index=False)

    metrics = BasicStrategyEvaluator(annualization_factor=252).evaluate(portfolio_pnl["net_pnl"], positions=weights)
    summary = pd.DataFrame([{**asdict(cfg), **metrics}])
    summary.to_csv(output_root / "summary.csv", index=False)
    _write_summary_txt(summary, attribution.summary, output_root)
    return summary


def _write_static_diagnostics(
    panels: DailyEodPanels,
    residuals: pd.DataFrame,
    exposures: pd.DataFrame,
    state: ResidualStateResult,
    target: pd.DataFrame,
    output_root: Path,
) -> None:
    panels.returns.to_csv(output_root / "input_returns.csv")
    residuals.to_csv(output_root / "rolling_residual_returns.csv")
    exposures.to_csv(output_root / "rolling_exposures.csv")
    state.features.to_csv(output_root / "residual_state_features.csv")
    state.trend_score.to_csv(output_root / "trend_scores.csv")
    state.displacement_score.to_csv(output_root / "displacement_scores.csv")
    target.to_csv(output_root / "full_regime_target.csv")
    _coverage_diagnostics(panels, residuals, state, target).to_csv(output_root / "data_coverage.csv", index=False)
    _feature_coverage(state.features).to_csv(output_root / "feature_coverage.csv", index=False)
    _target_balance(target).to_csv(output_root / "target_balance_by_symbol.csv", index=False)


def _write_fold_artifacts(
    fold_root: Path,
    probabilities: pd.DataFrame,
    target: pd.DataFrame,
    signal_result: HybridResidualSignalResult,
    backtest: FactorHedgedBacktestResult,
    attribution,
    fold_row: dict[str, object],
    pred_diag: dict[str, object],
) -> None:
    probabilities.to_csv(fold_root / "regime_probabilities.csv")
    target.to_csv(fold_root / "regime_target.csv")
    signal_result.signals.to_csv(fold_root / "stock_signals.csv")
    signal_result.modes.to_csv(fold_root / "modes.csv")
    backtest.target_weights.to_csv(fold_root / "target_weights.csv")
    backtest.portfolio_pnl.to_csv(fold_root / "portfolio_pnl.csv")
    backtest.exposure_diagnostics.to_csv(fold_root / "exposure_diagnostics.csv")
    attribution.summary.to_csv(fold_root / "mode_attribution_summary.csv", index=False)
    pd.DataFrame([fold_row]).to_csv(fold_root / "fold_metrics.csv", index=False)
    pd.DataFrame([pred_diag]).to_csv(fold_root / "prediction_diagnostics.csv", index=False)


def _slice_state(state: ResidualStateResult, index: pd.Index) -> ResidualStateResult:
    return ResidualStateResult(
        features=state.features.loc[index],
        residual_level=state.residual_level.loc[index],
        displacement_score=state.displacement_score.loc[index],
        trend_score=state.trend_score.loc[index],
        trend_slope=state.trend_slope.loc[index],
        trend_r2=state.trend_r2.loc[index],
        residual_volatility=state.residual_volatility.loc[index],
        relative_volume=state.relative_volume.loc[index] if state.relative_volume is not None else None,
        dollar_volume_zscore=state.dollar_volume_zscore.loc[index] if state.dollar_volume_zscore is not None else None,
        ou_s_score=state.ou_s_score.loc[index] if state.ou_s_score is not None else None,
        ou_mean_reversion_days=state.ou_mean_reversion_days.loc[index] if state.ou_mean_reversion_days is not None else None,
    )


def _factor_beta_panel(exposures: pd.DataFrame, index: pd.Index, factor: str) -> pd.DataFrame:
    return pd.DataFrame({stock: exposures[f"{stock}_{factor}"] for stock in TECH_STOCKS}).reindex(index)


def _date_index_between(index: pd.Index, start_date: date, end_date: date) -> pd.Index:
    ts_index = pd.DatetimeIndex(index)
    return ts_index[(ts_index >= pd.Timestamp(start_date)) & (ts_index <= pd.Timestamp(end_date))]


def _concat_dedup(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    return out.loc[~out.index.duplicated(keep="last")]


def _prediction_diagnostics(
    probabilities: pd.DataFrame, target: pd.DataFrame, signal_result: HybridResidualSignalResult
) -> dict[str, object]:
    aligned_target = target.reindex(index=probabilities.index, columns=probabilities.columns)
    valid = probabilities.notna() & aligned_target.notna()
    pred = probabilities >= 0.5
    y = aligned_target.eq(1.0)
    correct = pred.eq(y) & valid
    brier = (probabilities - aligned_target) ** 2
    return {
        "valid_prediction_count": int(valid.sum().sum()),
        "trend_label_count": int((aligned_target.eq(1.0) & valid).sum().sum()),
        "mean_reversion_label_count": int((aligned_target.eq(0.0) & valid).sum().sum()),
        "accuracy_50": float(correct.sum().sum() / valid.sum().sum()) if valid.sum().sum() else float("nan"),
        "brier_score": float(brier.where(valid).stack().mean()) if valid.sum().sum() else float("nan"),
        "mean_probability": float(probabilities.stack().mean()),
        "trend_mode_days": int(signal_result.modes.eq("trend").sum().sum()),
        "mean_reversion_mode_days": int(signal_result.modes.eq("mean_reversion").sum().sum()),
        "active_signal_days": int(signal_result.signals.ne(0.0).sum().sum()),
    }


def _prediction_diagnostics_by_symbol(probabilities: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in probabilities.columns:
        p = probabilities[symbol]
        y = target[symbol]
        valid = p.notna() & y.notna()
        if valid.any():
            rows.append(
                {
                    "symbol": symbol,
                    "valid_count": int(valid.sum()),
                    "trend_label_count": int(y.loc[valid].eq(1.0).sum()),
                    "mean_reversion_label_count": int(y.loc[valid].eq(0.0).sum()),
                    "accuracy_50": float(((p.loc[valid] >= 0.5) == y.loc[valid].eq(1.0)).mean()),
                    "brier_score": float(((p.loc[valid] - y.loc[valid]) ** 2).mean()),
                    "mean_probability": float(p.loc[valid].mean()),
                    "probability_std": float(p.loc[valid].std()),
                }
            )
    return pd.DataFrame(rows)


def _signal_diagnostics_by_symbol(signals: pd.DataFrame, modes: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in signals.columns:
        signal = signals[symbol]
        mode = modes[symbol]
        rows.append(
            {
                "symbol": symbol,
                "active_days": int(signal.ne(0.0).sum()),
                "long_days": int(signal.gt(0.0).sum()),
                "short_days": int(signal.lt(0.0).sum()),
                "trend_days": int(mode.eq("trend").sum()),
                "mean_reversion_days": int(mode.eq("mean_reversion").sum()),
                "signal_changes": int(signal.diff().fillna(signal).ne(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _coverage_diagnostics(
    panels: DailyEodPanels, residuals: pd.DataFrame, state: ResidualStateResult, target: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in TECH_STOCKS:
        rows.append(
            {
                "symbol": symbol,
                "return_obs": int(panels.returns[symbol].notna().sum()),
                "residual_obs": int(residuals[symbol].notna().sum()),
                "trend_score_obs": int(state.trend_score[symbol].notna().sum()),
                "displacement_score_obs": int(state.displacement_score[symbol].notna().sum()),
                "relative_volume_obs": int(state.relative_volume[symbol].notna().sum()) if state.relative_volume is not None else 0,
                "target_obs": int(target[symbol].notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def _feature_coverage(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol, feature in features.columns:
        series = features[(symbol, feature)]
        rows.append(
            {
                "symbol": symbol,
                "feature": feature,
                "non_null_count": int(series.notna().sum()),
                "non_null_rate": float(series.notna().mean()),
            }
        )
    return pd.DataFrame(rows)


def _target_balance(target: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in target.columns:
        valid = target[symbol].dropna()
        rows.append(
            {
                "symbol": symbol,
                "target_count": int(len(valid)),
                "trend_count": int(valid.eq(1.0).sum()),
                "mean_reversion_count": int(valid.eq(0.0).sum()),
                "trend_share": float(valid.eq(1.0).mean()) if len(valid) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _mode_counts(modes: pd.DataFrame) -> dict[str, int]:
    counts = modes.stack().value_counts()
    return {
        "trend_cells": int(counts.get("trend", 0)),
        "mean_reversion_cells": int(counts.get("mean_reversion", 0)),
        "flat_cells": int(counts.get("flat", 0)),
    }


def _write_config(cfg: DiagnosticConfig, output_root: Path) -> None:
    pd.DataFrame([asdict(cfg)]).to_csv(output_root / "config.csv", index=False)


def _write_summary_txt(summary: pd.DataFrame, mode_summary: pd.DataFrame, output_root: Path) -> None:
    lines = ["Hybrid residual diagnostics", "", "Overall summary:", summary.to_string(index=False), "", "Mode attribution:", mode_summary.to_string(index=False)]
    (output_root / "summary.txt").write_text("\n".join(lines), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full daily hybrid residual diagnostics.")
    parser.add_argument("--refresh-data", action="store_true", help="Refresh raw ThetaData EOD cache before running.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    result = run(refresh_data=args.refresh_data)
    print(result.to_string(index=False))
    print(f"Saved diagnostics to {OUTPUT_ROOT}")
