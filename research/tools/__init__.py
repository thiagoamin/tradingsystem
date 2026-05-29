"""Research tools package."""

from research.tools.backtest import BacktestEngine, FactorHedgedBacktestResult, FactorHedgedDailyBacktestEngine
from research.tools.evaluation import (
    BasicStrategyEvaluator,
    HybridModeAttributionEvaluator,
    ModeAttributionResult,
    StrategyEvaluator,
)
from research.tools.experiments import ExperimentConfig, TrainTestSlice, WalkForwardPlan, run_experiment
from research.tools.predictor import (
    PanelPredictor,
    ResidualRegimePredictor,
    build_residual_regime_target,
)
from research.tools.processing import (
    DailyEodPanels,
    StockSplit,
    apply_stock_split_adjustments,
    build_daily_eod_panels,
    build_split_adjustment_factors,
)
from research.tools.strategy import (
    HybridResidualSignalResult,
    HybridResidualStrategy,
    OUSScoreStrategy,
    PanelStrategy,
    Strategy,
)
from research.tools.transformer import (
    FactorOUScoreResult,
    OUEstimate,
    OUEstimator,
    OUScoreResult,
    PanelTransformer,
    ResidualStateResult,
    ResidualStateTransformer,
    RollingAssignedEtfOUScoreModel,
    RollingOUScoreModel,
    Transformer,
)

__all__ = [
    "DailyEodPanels",
    "BacktestEngine",
    "BasicStrategyEvaluator",
    "ExperimentConfig",
    "FactorHedgedBacktestResult",
    "FactorHedgedDailyBacktestEngine",
    "FactorOUScoreResult",
    "HybridResidualSignalResult",
    "HybridResidualStrategy",
    "HybridModeAttributionEvaluator",
    "ModeAttributionResult",
    "OUSScoreStrategy",
    "PanelPredictor",
    "PanelStrategy",
    "PanelTransformer",
    "OUEstimate",
    "OUEstimator",
    "OUScoreResult",
    "ResidualRegimePredictor",
    "ResidualStateResult",
    "ResidualStateTransformer",
    "RollingOUScoreModel",
    "RollingAssignedEtfOUScoreModel",
    "StockSplit",
    "Strategy",
    "StrategyEvaluator",
    "Transformer",
    "TrainTestSlice",
    "WalkForwardPlan",
    "apply_stock_split_adjustments",
    "build_daily_eod_panels",
    "build_residual_regime_target",
    "build_split_adjustment_factors",
    "run_experiment",
]
