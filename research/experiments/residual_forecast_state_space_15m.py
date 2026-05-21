from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, time
from pathlib import Path

import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.backtest import SimpleBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator
from research.tools.experiments import ExperimentConfig, WalkForwardPlan, business_days, run_experiment
from research.tools.predictor import RecursiveLeastSquaresResidualPredictor
from research.tools.processing import (
    QuoteVariablePanels,
    ReturnsConfig,
    TradeVariablePanels,
    build_quote_variables,
    build_residual_forecast_features,
    build_returns,
    build_trade_variables,
)
from research.tools.strategy import ForecastZScoreStrategy, ResidualVariableStrategy
from research.tools.transformer.residualization import FactorResidualizationModel, FactorSpec, RidgeExposureEstimator


@dataclass(frozen=True)
class ModelSpec:
    name: str
    use_predictor: bool
    forgetting_factor: float = 0.98
    forecast_entry_z: float = 1.0
    forecast_exit_z: float = 0.25
    forecast_z_window: int = 8
    min_hold_bars: int = 1
    allow_reversal: bool = True
    invert_signal: bool = False


@dataclass
class ResidualForecastState:
    residualizer: FactorResidualizationModel
    predictor: RecursiveLeastSquaresResidualPredictor | None = None


STOCKS = ["AAPL", "MSFT", "NVDA"]
FACTORS = ["SPY", "XLK", "QQQ"]
SYMBOLS = STOCKS + FACTORS
FORECAST_FEATURES = (
    "spread_bps",
    "imbalance",
    "microprice_pressure",
    "signed_volume_imbalance",
    "vwap_gap",
)
MODEL_SPECS = [
    ModelSpec(name="baseline_residual_zscore", use_predictor=False),
    ModelSpec(
        name="state_space_ff0995_e15_hold2_inv",
        use_predictor=True,
        forgetting_factor=0.995,
        forecast_entry_z=1.5,
        min_hold_bars=2,
        allow_reversal=False,
        invert_signal=True,
    ),
    ModelSpec(
        name="state_space_ff1_e2_hold2_inv",
        use_predictor=True,
        forgetting_factor=1.0,
        forecast_entry_z=2.0,
        forecast_exit_z=0.5,
        min_hold_bars=2,
        allow_reversal=False,
        invert_signal=True,
    ),
]


def build_experiment_config() -> ExperimentConfig:
    return ExperimentConfig(
        mode="walk_forward",
        start_date=date(2019, 1, 2),
        end_date=date(2019, 6, 28),
        horizons=["15m"],
        output_root=Path("research/experiment_outputs/residual_forecast_state_space_15m"),
        walk_forward=WalkForwardPlan(train_window_days=60, test_window_days=20, step_days=20, retrain_every_n_folds=1),
    )


def run(cfg: ExperimentConfig | None = None) -> pd.DataFrame:
    cfg = cfg or build_experiment_config()
    fetcher = ThetaDataFetcher(dataframe_type="pandas")
    returns_cache: dict[tuple[str, date, date], pd.DataFrame] = {}
    variables_cache: dict[tuple[str, date, date], QuoteVariablePanels] = {}
    trade_variables_cache: dict[tuple[str, date, date], TradeVariablePanels] = {}
    diagnostics_context: dict[str, pd.DataFrame | list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]] = {}

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

    def make_build_returns_fn(model_spec: ModelSpec):
        def build_returns_fn(horizon: str, start_date: date, end_date: date) -> pd.DataFrame:
            key = (horizon, start_date, end_date)
            if key not in returns_cache:
                config = returns_config_for_horizon(horizon)
                frames: list[pd.DataFrame] = []
                for day in business_days(start_date, end_date):
                    day_returns = build_returns(config=config, fetcher=fetcher, symbols=SYMBOLS, date_=day)
                    if not day_returns.empty:
                        frames.append(day_returns)
                if not frames:
                    raise ValueError(f"No return data was fetched for {start_date} to {end_date}.")
                returns_cache[key] = _dedupe_index(pd.concat(frames).sort_index())
            if model_spec.use_predictor and key not in variables_cache:
                variables_cache[key] = build_variables_for_range(horizon, start_date, end_date, returns_cache[key].index)
            if model_spec.use_predictor and key not in trade_variables_cache:
                trade_variables_cache[key] = build_trade_variables_for_range(
                    horizon=horizon,
                    start_date=start_date,
                    end_date=end_date,
                    index=returns_cache[key].index,
                    quote_variables=variables_cache[key],
                )
            return returns_cache[key].copy()

        return build_returns_fn

    def build_variables_for_range(horizon: str, start_date: date, end_date: date, index: pd.Index) -> QuoteVariablePanels:
        config = returns_config_for_horizon(horizon)
        by_name: dict[str, list[pd.DataFrame]] = {}
        for day in business_days(start_date, end_date):
            day_variables = build_quote_variables(config=config, fetcher=fetcher, symbols=SYMBOLS, date_=day)
            for name, panel in day_variables.items():
                by_name.setdefault(name, []).append(panel)
        return {name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index) for name, frames in by_name.items()}

    def build_trade_variables_for_range(
        horizon: str,
        start_date: date,
        end_date: date,
        index: pd.Index,
        quote_variables: QuoteVariablePanels,
    ) -> TradeVariablePanels:
        config = returns_config_for_horizon(horizon)
        by_name: dict[str, list[pd.DataFrame]] = {}
        quote_mid = quote_variables["mid"]
        for day in business_days(start_date, end_date):
            day_index = quote_mid.index[quote_mid.index.date == day]
            day_trade_variables = build_trade_variables(
                config=config,
                fetcher=fetcher,
                symbols=SYMBOLS,
                date_=day,
                variables=("signed_volume_imbalance", "vwap_gap"),
                quote_mid=quote_mid.reindex(day_index),
            )
            for name, panel in day_trade_variables.items():
                by_name.setdefault(name, []).append(panel)
        return {name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index) for name, frames in by_name.items()}

    def variables_for_index(horizon: str, index: pd.Index) -> QuoteVariablePanels:
        by_name: dict[str, list[pd.DataFrame]] = {}
        for (cached_horizon, _, _), panels in variables_cache.items():
            if cached_horizon != horizon:
                continue
            for name, panel in panels.items():
                by_name.setdefault(name, []).append(panel)
        return {name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index=index, columns=STOCKS) for name, frames in by_name.items()}

    def trade_variables_for_index(horizon: str, index: pd.Index) -> TradeVariablePanels:
        by_name: dict[str, list[pd.DataFrame]] = {}
        for (cached_horizon, _, _), panels in trade_variables_cache.items():
            if cached_horizon != horizon:
                continue
            for name, panel in panels.items():
                by_name.setdefault(name, []).append(panel)
        return {name: _dedupe_index(pd.concat(frames).sort_index()).reindex(index=index, columns=STOCKS) for name, frames in by_name.items()}

    def make_fit_transformer_fn(model_spec: ModelSpec):
        def fit_transformer_fn(train_returns: pd.DataFrame) -> ResidualForecastState:
            residualizer = FactorResidualizationModel(
                FactorSpec({stock: FACTORS for stock in STOCKS}),
                RidgeExposureEstimator(alpha=1.0),
            ).fit(train_returns)
            train_residuals = residualizer.transform(train_returns)
            if not model_spec.use_predictor:
                return ResidualForecastState(residualizer=residualizer)
            predictor = RecursiveLeastSquaresResidualPredictor(
                forgetting_factor=model_spec.forgetting_factor,
                ridge=1e-3,
                min_obs=20,
            )
            features = build_residual_forecast_features(
                residuals=train_residuals,
                quote_variables=variables_for_index("15m", train_residuals.index),
                trade_variables=trade_variables_for_index("15m", train_residuals.index),
                variable_names=FORECAST_FEATURES,
                residual_window=6,
            )
            predictor.fit(features=features, target=train_residuals.shift(-1))
            return ResidualForecastState(residualizer=residualizer, predictor=predictor)

        return fit_transformer_fn

    def make_transform_fn(model_spec: ModelSpec):
        def transform_fn(state: ResidualForecastState, returns: pd.DataFrame) -> pd.DataFrame:
            residuals = state.residualizer.transform(returns)
            if not model_spec.use_predictor:
                return residuals
            if state.predictor is None:
                raise RuntimeError("predictor state is missing")
            features = build_residual_forecast_features(
                residuals=residuals,
                quote_variables=variables_for_index("15m", residuals.index),
                trade_variables=trade_variables_for_index("15m", residuals.index),
                variable_names=FORECAST_FEATURES,
                residual_window=6,
            )
            forecasts = state.predictor.predict(features).reindex(index=residuals.index, columns=STOCKS)
            diagnostics_context["latest_forecasts"] = forecasts
            diagnostics_context["latest_residuals"] = residuals
            return forecasts

        return transform_fn

    def make_generate_positions_fn(model_spec: ModelSpec):
        def generate_positions_fn(transformed_history: pd.DataFrame, transformed_test: pd.DataFrame, _: str) -> pd.DataFrame:
            if model_spec.use_predictor:
                positions = ForecastZScoreStrategy(
                    z_window=model_spec.forecast_z_window,
                    entry_z=model_spec.forecast_entry_z,
                    exit_z=model_spec.forecast_exit_z,
                    min_hold_bars=model_spec.min_hold_bars,
                    allow_reversal=model_spec.allow_reversal,
                    invert_signal=model_spec.invert_signal,
                ).generate(transformed_history)
            else:
                positions = ResidualVariableStrategy(z_window=8, entry_z=1.5, exit_z=0.25).generate(transformed_history)
            return positions.loc[transformed_test.index]

        return generate_positions_fn

    def backtest_fn(positions: pd.DataFrame, test_returns: pd.DataFrame) -> pd.DataFrame:
        return SimpleBacktestEngine(position_lag=1, normalize_exposure=True).run(positions=positions, returns=test_returns[STOCKS])

    def make_evaluate_fn(model_spec: ModelSpec):
        fold_panels: list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = []

        def evaluate_fn(pnl: pd.DataFrame | pd.Series, positions: pd.DataFrame) -> dict[str, float]:
            metrics = BasicStrategyEvaluator(annualization_factor=None).evaluate(pnl, positions=positions)
            if not model_spec.use_predictor:
                return metrics
            pnl_df = pnl.to_frame() if isinstance(pnl, pd.Series) else pnl
            latest_forecasts = diagnostics_context.get("latest_forecasts")
            latest_residuals = diagnostics_context.get("latest_residuals")
            if isinstance(latest_forecasts, pd.DataFrame) and isinstance(latest_residuals, pd.DataFrame):
                if positions.index.equals(latest_forecasts.index):
                    fold_panels.append((latest_forecasts.copy(), latest_residuals.copy(), pnl_df.copy()))
                    metrics.update(
                        forecast_diagnostics(
                            forecasts=latest_forecasts,
                            residuals=latest_residuals,
                            pnl=pnl_df,
                            invert_signal=model_spec.invert_signal,
                        )
                    )
                    return metrics
            if fold_panels:
                forecasts = _dedupe_index(pd.concat([panel[0] for panel in fold_panels]).sort_index())
                residuals = _dedupe_index(pd.concat([panel[1] for panel in fold_panels]).sort_index())
                pnl_all = _dedupe_index(pd.concat([panel[2] for panel in fold_panels]).sort_index())
                metrics.update(
                    forecast_diagnostics(
                        forecasts=forecasts,
                        residuals=residuals,
                        pnl=pnl_all,
                        invert_signal=model_spec.invert_signal,
                    )
                )
            return metrics

        return evaluate_fn

    def write_state_fn(state: ResidualForecastState, output_dir: Path) -> None:
        state.residualizer.exposures.to_csv(output_dir / "residual_exposures.csv")
        if state.predictor is not None:
            state.predictor.coefficients.to_csv(output_dir / "state_space_coefficients.csv")

    try:
        summaries: list[pd.DataFrame] = []
        for model_spec in MODEL_SPECS:
            model_cfg = replace(cfg, output_root=cfg.output_root / model_spec.name)
            summary = run_experiment(
                cfg=model_cfg,
                build_returns_fn=make_build_returns_fn(model_spec),
                fit_transformer_fn=make_fit_transformer_fn(model_spec),
                transform_fn=make_transform_fn(model_spec),
                generate_positions_fn=make_generate_positions_fn(model_spec),
                backtest_fn=backtest_fn,
                evaluate_fn=make_evaluate_fn(model_spec),
                write_state_fn=write_state_fn,
            )
            summary.insert(0, "model", model_spec.name)
            summaries.append(summary)
        combined = pd.concat(summaries, ignore_index=True)
        cfg.output_root.mkdir(parents=True, exist_ok=True)
        combined.to_csv(cfg.output_root / "model_comparison.csv", index=False)
        return combined
    finally:
        close_method = getattr(fetcher.client, "close", None)
        if callable(close_method):
            close_method()


def _dedupe_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.has_duplicates:
        return df[~df.index.duplicated(keep="last")]
    return df


def forecast_diagnostics(
    forecasts: pd.DataFrame,
    residuals: pd.DataFrame,
    pnl: pd.DataFrame,
    invert_signal: bool,
) -> dict[str, float]:
    target = residuals.shift(-1)
    raw_forecast = forecasts.reindex(index=target.index, columns=target.columns)
    effective_forecast = -raw_forecast if invert_signal else raw_forecast
    metrics = {
        "forecast_target_corr": _stacked_corr(raw_forecast, target),
        "inverted_forecast_target_corr": _stacked_corr(-raw_forecast, target),
        "effective_forecast_target_corr": _stacked_corr(effective_forecast, target),
    }
    metrics.update(_forecast_quantile_pnl(effective_forecast=effective_forecast, pnl=pnl))
    return metrics


def _stacked_corr(left: pd.DataFrame, right: pd.DataFrame) -> float:
    aligned = pd.concat([left.stack().rename("left"), right.stack().rename("right")], axis=1).dropna()
    if len(aligned) < 2:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def _forecast_quantile_pnl(effective_forecast: pd.DataFrame, pnl: pd.DataFrame) -> dict[str, float]:
    signal_for_pnl = effective_forecast.shift(1).reindex(index=pnl.index, columns=pnl.columns)
    stacked = pd.concat(
        [signal_for_pnl.stack().rename("forecast"), pnl.stack().rename("pnl")],
        axis=1,
    ).dropna()
    result = {f"forecast_q{idx}_mean_pnl": float("nan") for idx in range(1, 6)}
    if len(stacked) < 5 or stacked["forecast"].nunique() < 5:
        return result
    try:
        quantiles = pd.qcut(stacked["forecast"], q=5, labels=False, duplicates="drop")
    except ValueError:
        return result
    grouped = stacked.groupby(quantiles)["pnl"].mean()
    for quantile_idx, value in grouped.items():
        result[f"forecast_q{int(quantile_idx) + 1}_mean_pnl"] = float(value)
    return result


def main() -> None:
    summary = run()
    print(summary)
    print(f"Saved outputs to {build_experiment_config().output_root}")


if __name__ == "__main__":
    main()
