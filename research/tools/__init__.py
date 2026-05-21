"""Research tools package."""

from research.tools.backtest import BacktestEngine
from research.tools.backtest import SimpleBacktestEngine
from research.tools.evaluation import BasicStrategyEvaluator, StrategyEvaluator
from research.tools.experiments import ExperimentConfig, TrainTestSlice, WalkForwardPlan, run_experiment
from research.tools.predictor import PanelPredictor, RecursiveLeastSquaresResidualPredictor
from research.tools.processing import (
    QuoteVariablePanels,
    ReturnsConfig,
    TradeVariablePanels,
    build_quote_variables,
    build_residual_forecast_features,
    build_returns,
    build_trade_variables,
)
from research.tools.strategy import ForecastZScoreStrategy, PanelStrategy, ResidualVariableStrategy, ResidualZScoreStrategy, Strategy
from research.tools.transformer import PanelTransformer, Transformer

__all__ = [
    "BacktestEngine",
    "BasicStrategyEvaluator",
    "ExperimentConfig",
    "ForecastZScoreStrategy",
    "PanelPredictor",
    "PanelStrategy",
    "PanelTransformer",
    "QuoteVariablePanels",
    "RecursiveLeastSquaresResidualPredictor",
    "ResidualVariableStrategy",
    "ResidualZScoreStrategy",
    "ReturnsConfig",
    "SimpleBacktestEngine",
    "Strategy",
    "StrategyEvaluator",
    "Transformer",
    "TradeVariablePanels",
    "TrainTestSlice",
    "WalkForwardPlan",
    "build_quote_variables",
    "build_residual_forecast_features",
    "build_returns",
    "build_trade_variables",
    "run_experiment",
]
