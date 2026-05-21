from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path

import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.backtest import SimpleBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.experiments import ExperimentConfig, WalkForwardPlan, run_experiment
from research.tools.processing import ReturnsConfig, build_returns
from research.tools.strategy import ResidualZScoreStrategy
from research.tools.transformer.residualization import (
    FactorResidualizationModel,
    FactorSpec,
    RidgeExposureEstimator,
)


def _z_window_for_horizon(horizon: str) -> int:
    minutes_by_horizon = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
    if horizon not in minutes_by_horizon:
        raise ValueError(f"Unsupported horizon {horizon!r}.")
    return max(390 // minutes_by_horizon[horizon], 2)


def _business_days(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def build_experiment_config() -> ExperimentConfig:
    return ExperimentConfig(
        mode="walk_forward",
        start_date=date(2019, 1, 2),
        end_date=date(2019, 6, 28),
        test_start_date=date(2019, 4, 1),
        horizons=["5m"],
        output_root=Path("research/experiment_outputs/residual_strategy_6m"),
        walk_forward=WalkForwardPlan(
            train_window_days=60,
            test_window_days=20,
            step_days=20,
            anchored=False,
            retrain_every_n_folds=1,
        ),
    )


def run(cfg: ExperimentConfig | None = None) -> pd.DataFrame:
    cfg = cfg or build_experiment_config()
    stocks = ["AAPL", "MSFT", "NVDA"]
    factors = ["SPY", "XLK", "QQQ"]
    symbols = stocks + factors
    session_start = time(9, 30)
    session_end = time(16, 0)
    exclude_open_minutes = 30
    exclude_close_minutes = 30
    ridge_alpha = 1.0
    entry_z = 2.0
    exit_z = 0.5
    fetcher = ThetaDataFetcher(dataframe_type="pandas")

    def returns_config_for_horizon(horizon: str) -> ReturnsConfig:
        return ReturnsConfig(
            horizon=horizon,
            price_source="quote_mid",
            return_type="log",
            session_start=session_start,
            session_end=session_end,
            exclude_open_minutes=exclude_open_minutes,
            exclude_close_minutes=exclude_close_minutes,
        )

    def build_returns_fn(horizon: str, start_date: date, end_date: date) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        config = returns_config_for_horizon(horizon)
        for day in _business_days(start_date, end_date):
            day_df = build_returns(config=config, fetcher=fetcher, symbols=symbols, date_=day)
            if not day_df.empty:
                frames.append(day_df)
        if not frames:
            raise ValueError(f"No return data was fetched for {start_date} to {end_date}.")
        return pd.concat(frames).sort_index()

    def fit_transformer_fn(train_returns: pd.DataFrame) -> FactorResidualizationModel:
        spec = FactorSpec({stock: factors for stock in stocks})
        model = FactorResidualizationModel(spec, RidgeExposureEstimator(alpha=ridge_alpha))
        model.fit(train_returns)
        return model

    def transform_fn(transformer_state: FactorResidualizationModel, returns: pd.DataFrame) -> pd.DataFrame:
        return transformer_state.transform(returns)

    def generate_positions_fn(
        transformed_history: pd.DataFrame, transformed_test: pd.DataFrame, horizon: str
    ) -> pd.DataFrame:
        strategy = ResidualZScoreStrategy(
            z_window=_z_window_for_horizon(horizon),
            entry_z=entry_z,
            exit_z=exit_z,
        )
        return strategy.generate(transformed_history).loc[transformed_test.index]

    def backtest_fn(positions: pd.DataFrame, test_returns: pd.DataFrame) -> pd.DataFrame:
        return SimpleBacktestEngine(position_lag=1, normalize_exposure=True).run(
            positions=positions,
            returns=test_returns[stocks],
        )

    def evaluate_fn(pnl: pd.DataFrame | pd.Series, positions: pd.DataFrame) -> dict[str, float]:
        return BasicStrategyEvaluator(annualization_factor=None).evaluate(pnl, positions=positions)

    def write_state_fn(state: FactorResidualizationModel, output_dir: Path) -> None:
        state.exposures.to_csv(output_dir / "transformer_state_exposures.csv")

    try:
        return run_experiment(
            cfg=cfg,
            build_returns_fn=build_returns_fn,
            fit_transformer_fn=fit_transformer_fn,
            transform_fn=transform_fn,
            generate_positions_fn=generate_positions_fn,
            backtest_fn=backtest_fn,
            evaluate_fn=evaluate_fn,
            write_state_fn=write_state_fn,
        )
    finally:
        close_method = getattr(fetcher.client, "close", None)
        if callable(close_method):
            close_method()


def main() -> None:
    summary = run()
    print(summary)
    print(f"Saved outputs to {build_experiment_config().output_root}")


if __name__ == "__main__":
    main()
