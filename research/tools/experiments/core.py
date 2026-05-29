from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

import pandas as pd

Mode = Literal["single_split", "walk_forward"]

BuildReturnsFn = Callable[[str, date, date], pd.DataFrame]
FitTransformerFn = Callable[[pd.DataFrame], Any]
TransformFn = Callable[[Any, pd.DataFrame], pd.DataFrame]
GeneratePositionsFn = Callable[[pd.DataFrame, pd.DataFrame, str], pd.DataFrame]
BacktestFn = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame | pd.Series]
EvaluateFn = Callable[[pd.DataFrame | pd.Series, pd.DataFrame], dict[str, float]]
WriteStateFn = Callable[[Any, Path], None]


@dataclass(frozen=True)
class TrainTestSlice:
    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    should_retrain: bool


def business_days(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def resolve_test_start_date(start_date: date, end_date: date, requested: date | None) -> date:
    days = business_days(start_date, end_date)
    if len(days) < 2:
        raise ValueError("Date range must contain at least two business days for train/test split.")
    fallback = days[len(days) // 2]
    if requested is None:
        return fallback
    if requested < start_date or requested > end_date:
        return fallback
    for day in days:
        if day >= requested:
            return day
    return fallback


@dataclass(frozen=True)
class WalkForwardPlan:
    train_window_days: int = 60
    test_window_days: int = 20
    step_days: int = 20
    anchored: bool = False
    retrain_every_n_folds: int = 1

    def __post_init__(self) -> None:
        if self.train_window_days < 2:
            raise ValueError("train_window_days must be >= 2")
        if self.test_window_days < 1:
            raise ValueError("test_window_days must be >= 1")
        if self.step_days < 1:
            raise ValueError("step_days must be >= 1")
        if self.retrain_every_n_folds < 1:
            raise ValueError("retrain_every_n_folds must be >= 1")

    def build_slices(self, start_date: date, end_date: date) -> list[TrainTestSlice]:
        days = business_days(start_date, end_date)
        if len(days) < self.train_window_days + self.test_window_days:
            raise ValueError("Date range is too short for configured walk-forward windows.")
        slices: list[TrainTestSlice] = []
        fold_id = 0
        test_start_idx = self.train_window_days
        while test_start_idx < len(days):
            train_start_idx = 0 if self.anchored else max(0, test_start_idx - self.train_window_days)
            train_end_idx = test_start_idx - 1
            test_end_idx = min(test_start_idx + self.test_window_days - 1, len(days) - 1)
            if train_end_idx <= train_start_idx:
                break
            slices.append(
                TrainTestSlice(
                    fold_id=fold_id,
                    train_start=days[train_start_idx],
                    train_end=days[train_end_idx],
                    test_start=days[test_start_idx],
                    test_end=days[test_end_idx],
                    should_retrain=(fold_id % self.retrain_every_n_folds == 0),
                )
            )
            fold_id += 1
            test_start_idx += self.step_days
        if not slices:
            raise ValueError("No walk-forward slices were generated with the current configuration.")
        return slices


@dataclass(frozen=True)
class ExperimentConfig:
    mode: Mode = "walk_forward"
    start_date: date = date(2019, 1, 2)
    end_date: date = date(2019, 6, 28)
    test_start_date: date | None = None
    horizons: list[str] = field(default_factory=lambda: ["5m"])
    output_root: Path = Path("research/experiment_outputs/default_experiment")
    walk_forward: WalkForwardPlan = field(default_factory=WalkForwardPlan)


def _write_common_artifacts(
    output_dir: Path,
    train_returns: pd.DataFrame,
    test_returns: pd.DataFrame,
    train_transformed: pd.DataFrame,
    test_transformed: pd.DataFrame,
    positions: pd.DataFrame,
    pnl: pd.DataFrame | pd.Series,
    metrics: dict[str, float],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    train_returns.to_csv(output_dir / "train_returns.csv")
    test_returns.to_csv(output_dir / "test_returns.csv")
    train_transformed.to_csv(output_dir / "train_transformed.csv")
    test_transformed.to_csv(output_dir / "test_transformed.csv")
    positions.to_csv(output_dir / "test_positions.csv")
    if isinstance(pnl, pd.Series):
        pnl.to_csv(output_dir / "test_pnl.csv")
    else:
        pnl.to_csv(output_dir / "test_pnl.csv")
    pd.DataFrame([metrics]).to_csv(output_dir / "metrics.csv", index=False)


def _single_split_horizon(
    cfg: ExperimentConfig,
    horizon: str,
    split_test_start: date,
    build_returns_fn: BuildReturnsFn,
    fit_transformer_fn: FitTransformerFn,
    transform_fn: TransformFn,
    generate_positions_fn: GeneratePositionsFn,
    backtest_fn: BacktestFn,
    evaluate_fn: EvaluateFn,
    write_state_fn: WriteStateFn | None,
) -> dict[str, float | str]:
    train_end = split_test_start - timedelta(days=1)
    train_returns = build_returns_fn(horizon, cfg.start_date, train_end)
    test_returns = build_returns_fn(horizon, split_test_start, cfg.end_date)
    state = fit_transformer_fn(train_returns)
    train_transformed = transform_fn(state, train_returns)
    test_transformed = transform_fn(state, test_returns)
    transformed_history = pd.concat([train_transformed, test_transformed]).sort_index()
    test_positions = generate_positions_fn(transformed_history, test_transformed, horizon)
    pnl = backtest_fn(test_positions, test_returns)
    metrics = evaluate_fn(pnl, test_positions)
    out_dir = cfg.output_root / horizon
    _write_common_artifacts(
        out_dir, train_returns, test_returns, train_transformed, test_transformed, test_positions, pnl, metrics
    )
    if write_state_fn is not None:
        write_state_fn(state, out_dir)
    return {"horizon": horizon, "train_rows": float(len(train_returns)), "test_rows": float(len(test_returns)), **metrics}


def _walk_forward_horizon(
    cfg: ExperimentConfig,
    horizon: str,
    slices: list[TrainTestSlice],
    build_returns_fn: BuildReturnsFn,
    fit_transformer_fn: FitTransformerFn,
    transform_fn: TransformFn,
    generate_positions_fn: GeneratePositionsFn,
    backtest_fn: BacktestFn,
    evaluate_fn: EvaluateFn,
    write_state_fn: WriteStateFn | None,
) -> dict[str, float | str]:
    out_dir = cfg.output_root / horizon
    out_dir.mkdir(parents=True, exist_ok=True)
    state: Any = None
    fold_rows: list[dict[str, float | str]] = []
    oos_pnl_parts: list[pd.DataFrame | pd.Series] = []
    oos_position_parts: list[pd.DataFrame] = []
    for slc in slices:
        train_returns = build_returns_fn(horizon, slc.train_start, slc.train_end)
        if state is None or slc.should_retrain:
            state = fit_transformer_fn(train_returns)
            retrained = True
        else:
            retrained = False
        test_returns = build_returns_fn(horizon, slc.test_start, slc.test_end)
        train_transformed = transform_fn(state, train_returns)
        test_transformed = transform_fn(state, test_returns)
        transformed_history = pd.concat([train_transformed, test_transformed]).sort_index()
        test_positions = generate_positions_fn(transformed_history, test_transformed, horizon)
        pnl = backtest_fn(test_positions, test_returns)
        fold_metrics = evaluate_fn(pnl, test_positions)
        fold_rows.append(
            {
                "fold_id": float(slc.fold_id),
                "train_start": slc.train_start.isoformat(),
                "train_end": slc.train_end.isoformat(),
                "test_start": slc.test_start.isoformat(),
                "test_end": slc.test_end.isoformat(),
                "retrained": "yes" if retrained else "no",
                **fold_metrics,
            }
        )
        oos_pnl_parts.append(pnl)
        oos_position_parts.append(test_positions)
        fold_dir = out_dir / f"fold_{slc.fold_id:03d}"
        _write_common_artifacts(
            fold_dir,
            train_returns,
            test_returns,
            train_transformed,
            test_transformed,
            test_positions,
            pnl,
            fold_metrics,
        )
        if retrained and write_state_fn is not None:
            write_state_fn(state, fold_dir)
    if not oos_pnl_parts:
        raise ValueError("Walk-forward run produced no OOS pnl parts.")
    oos_pnl = pd.concat(oos_pnl_parts).sort_index()
    if oos_pnl.index.has_duplicates:
        oos_pnl = oos_pnl[~oos_pnl.index.duplicated(keep="first")]
    oos_positions = pd.concat(oos_position_parts).sort_index()
    if oos_positions.index.has_duplicates:
        oos_positions = oos_positions[~oos_positions.index.duplicated(keep="first")]
    oos_positions = oos_positions.reindex(oos_pnl.index)
    oos_metrics = evaluate_fn(oos_pnl, oos_positions)
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_metrics.csv", index=False)
    oos_pnl.to_csv(out_dir / "oos_test_pnl.csv")
    oos_positions.to_csv(out_dir / "oos_test_positions.csv")
    pd.DataFrame([oos_metrics]).to_csv(out_dir / "oos_metrics.csv", index=False)
    return {"horizon": horizon, "num_folds": float(len(slices)), **oos_metrics}


def run_experiment(
    cfg: ExperimentConfig,
    build_returns_fn: BuildReturnsFn,
    fit_transformer_fn: FitTransformerFn,
    transform_fn: TransformFn,
    generate_positions_fn: GeneratePositionsFn,
    backtest_fn: BacktestFn,
    evaluate_fn: EvaluateFn,
    write_state_fn: WriteStateFn | None = None,
) -> pd.DataFrame:
    cfg.output_root.mkdir(parents=True, exist_ok=True)
    if cfg.start_date >= cfg.end_date:
        raise ValueError(f"start_date must be before end_date. Got {cfg.start_date} >= {cfg.end_date}.")
    if cfg.mode == "single_split":
        split = resolve_test_start_date(cfg.start_date, cfg.end_date, cfg.test_start_date)
        rows = [
            _single_split_horizon(
                cfg,
                horizon,
                split,
                build_returns_fn,
                fit_transformer_fn,
                transform_fn,
                generate_positions_fn,
                backtest_fn,
                evaluate_fn,
                write_state_fn,
            )
            for horizon in cfg.horizons
        ]
    else:
        slices = cfg.walk_forward.build_slices(cfg.start_date, cfg.end_date)
        rows = [
            _walk_forward_horizon(
                cfg,
                horizon,
                slices,
                build_returns_fn,
                fit_transformer_fn,
                transform_fn,
                generate_positions_fn,
                backtest_fn,
                evaluate_fn,
                write_state_fn,
            )
            for horizon in cfg.horizons
        ]
    summary = pd.DataFrame(rows)
    summary.to_csv(cfg.output_root / "horizon_comparison.csv", index=False)
    return summary
