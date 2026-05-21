from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, time
from pathlib import Path

import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.backtest import SimpleBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.experiments import ExperimentConfig, WalkForwardPlan, business_days, run_experiment
from research.tools.processing import QuoteVariablePanels, ReturnsConfig, build_quote_variables, build_returns
from research.tools.strategy import ResidualVariableStrategy
from research.tools.transformer.residualization import FactorResidualizationModel, FactorSpec, RidgeExposureEstimator


@dataclass(frozen=True)
class StrategySpec:
    name: str
    max_spread_bps: float | None = None
    min_abs_microprice_pressure: float | None = None

    @property
    def uses_quote_variables(self) -> bool:
        return self.max_spread_bps is not None or self.min_abs_microprice_pressure is not None


STOCKS = ["AAPL", "MSFT", "NVDA"]
FACTORS = ["SPY", "XLK", "QQQ"]
SYMBOLS = STOCKS + FACTORS
STRATEGIES = [
    StrategySpec(name="residual_zscore"),
    StrategySpec(name="residual_spread_filter", max_spread_bps=15.0),
    StrategySpec(name="residual_spread_microprice", max_spread_bps=15.0, min_abs_microprice_pressure=0.05),
]


def build_experiment_config() -> ExperimentConfig:
    return ExperimentConfig(
        mode="walk_forward",
        start_date=date(2019, 1, 2),
        end_date=date(2019, 2, 28),
        horizons=["5m", "15m"],
        output_root=Path("research/experiment_outputs/residual_variable_strategy_comparison"),
        walk_forward=WalkForwardPlan(train_window_days=15, test_window_days=5, step_days=5, retrain_every_n_folds=1),
    )


def _z_window_for_horizon(horizon: str) -> int:
    minutes_by_horizon = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
    if horizon not in minutes_by_horizon:
        raise ValueError(f"Unsupported horizon {horizon!r}.")
    return max(390 // minutes_by_horizon[horizon], 2)


def run(cfg: ExperimentConfig | None = None) -> pd.DataFrame:
    cfg = cfg or build_experiment_config()
    fetcher = ThetaDataFetcher(dataframe_type="pandas")
    returns_cache: dict[tuple[str, date, date], pd.DataFrame] = {}
    variables_cache: dict[tuple[str, date, date], QuoteVariablePanels] = {}

    def returns_config_for_horizon(horizon: str) -> ReturnsConfig:
        return ReturnsConfig(
            horizon=horizon,
            price_source="quote_mid",
            return_type="log",
            session_start=time(9, 30),
            session_end=time(16, 0),
            exclude_open_minutes=30,
            exclude_close_minutes=30,
        )

    def make_build_returns_fn(strategy_spec: StrategySpec):
        def build_returns_fn(horizon: str, start_date: date, end_date: date) -> pd.DataFrame:
            key = (horizon, start_date, end_date)
            if key not in returns_cache:
                config = returns_config_for_horizon(horizon)
                return_frames: list[pd.DataFrame] = []
                for day in business_days(start_date, end_date):
                    day_returns = build_returns(config=config, fetcher=fetcher, symbols=SYMBOLS, date_=day)
                    if not day_returns.empty:
                        return_frames.append(day_returns)
                if not return_frames:
                    raise ValueError(f"No return data was fetched for {start_date} to {end_date}.")
                returns_cache[key] = _dedupe_index(pd.concat(return_frames).sort_index())
            if strategy_spec.uses_quote_variables and key not in variables_cache:
                variables_cache[key] = build_variables_for_range(horizon, start_date, end_date, returns_cache[key].index)
            return returns_cache[key].copy()

        return build_returns_fn

    def build_variables_for_range(horizon: str, start_date: date, end_date: date, index: pd.Index) -> QuoteVariablePanels:
        config = returns_config_for_horizon(horizon)
        variable_frames: dict[str, list[pd.DataFrame]] = {}
        for day in business_days(start_date, end_date):
            day_variables = build_quote_variables(config=config, fetcher=fetcher, symbols=SYMBOLS, date_=day)
            for name, panel in day_variables.items():
                variable_frames.setdefault(name, []).append(panel)
        return {
            name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index)
            for name, frames in variable_frames.items()
        }

    def variables_for_index(horizon: str, index: pd.Index) -> QuoteVariablePanels:
        by_name: dict[str, list[pd.DataFrame]] = {}
        for (cached_horizon, _, _), panels in variables_cache.items():
            if cached_horizon != horizon:
                continue
            for name, panel in panels.items():
                by_name.setdefault(name, []).append(panel)
        return {name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index=index, columns=STOCKS) for name, frames in by_name.items()}

    def fit_transformer_fn(train_returns: pd.DataFrame) -> FactorResidualizationModel:
        model = FactorResidualizationModel(FactorSpec({stock: FACTORS for stock in STOCKS}), RidgeExposureEstimator(alpha=1.0))
        model.fit(train_returns)
        return model

    def transform_fn(transformer_state: FactorResidualizationModel, returns: pd.DataFrame) -> pd.DataFrame:
        return transformer_state.transform(returns)

    def make_generate_positions_fn(strategy_spec: StrategySpec):
        def generate_positions_fn(transformed_history: pd.DataFrame, transformed_test: pd.DataFrame, horizon: str) -> pd.DataFrame:
            strategy = ResidualVariableStrategy(
                z_window=_z_window_for_horizon(horizon),
                entry_z=2.0,
                exit_z=0.5,
                max_spread_bps=strategy_spec.max_spread_bps,
                min_abs_microprice_pressure=strategy_spec.min_abs_microprice_pressure,
            )
            variables = variables_for_index(horizon, transformed_history.index) if strategy_spec.uses_quote_variables else None
            positions = strategy.generate(transformed_history, variables=variables)
            return positions.loc[transformed_test.index]

        return generate_positions_fn

    def backtest_fn(positions: pd.DataFrame, test_returns: pd.DataFrame) -> pd.DataFrame:
        return SimpleBacktestEngine(position_lag=1, normalize_exposure=True).run(positions=positions, returns=test_returns[STOCKS])

    def evaluate_fn(pnl: pd.DataFrame | pd.Series, positions: pd.DataFrame) -> dict[str, float]:
        return BasicStrategyEvaluator(annualization_factor=None).evaluate(pnl, positions=positions)

    def write_state_fn(state: FactorResidualizationModel, output_dir: Path) -> None:
        state.exposures.to_csv(output_dir / "residual_exposures.csv")

    try:
        summaries: list[pd.DataFrame] = []
        for strategy_spec in STRATEGIES:
            strategy_cfg = replace(cfg, output_root=cfg.output_root / strategy_spec.name)
            summary = run_experiment(
                cfg=strategy_cfg,
                build_returns_fn=make_build_returns_fn(strategy_spec),
                fit_transformer_fn=fit_transformer_fn,
                transform_fn=transform_fn,
                generate_positions_fn=make_generate_positions_fn(strategy_spec),
                backtest_fn=backtest_fn,
                evaluate_fn=evaluate_fn,
                write_state_fn=write_state_fn,
            )
            summary.insert(0, "strategy", strategy_spec.name)
            summaries.append(summary)
        combined = pd.concat(summaries, ignore_index=True)
        cfg.output_root.mkdir(parents=True, exist_ok=True)
        combined.to_csv(cfg.output_root / "strategy_horizon_comparison.csv", index=False)
        return combined
    finally:
        close_method = getattr(fetcher.client, "close", None)
        if callable(close_method):
            close_method()


def _dedupe_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.has_duplicates:
        return df[~df.index.duplicated(keep="last")]
    return df


def main() -> None:
    summary = run()
    print(summary)
    print(f"Saved outputs to {build_experiment_config().output_root}")


if __name__ == "__main__":
    main()
