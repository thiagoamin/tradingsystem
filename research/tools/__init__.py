"""Research tools package."""

from research.tools.contracts import (
    ComponentContract,
    DataRequirement,
    StrategyContract,
    StrategyRunContext,
    VariableSpec,
)
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
    "BacktestEngine",
    "BasicStrategyEvaluator",
    "ComponentContract",
    "DailyEodPanels",
    "DataRequirement",
    "ExperimentConfig",
    "FactorHedgedBacktestResult",
    "FactorHedgedDailyBacktestEngine",
    "FactorOUScoreResult",
    "HybridModeAttributionEvaluator",
    "HybridResidualSignalResult",
    "HybridResidualStrategy",
    "ModeAttributionResult",
    "OUEstimate",
    "OUEstimator",
    "OUSScoreStrategy",
    "OUScoreResult",
    "PanelPredictor",
    "PanelStrategy",
    "PanelTransformer",
    "ResidualRegimePredictor",
    "ResidualStateResult",
    "ResidualStateTransformer",
    "RollingAssignedEtfOUScoreModel",
    "RollingOUScoreModel",
    "StockSplit",
    "Strategy",
    "StrategyContract",
    "StrategyEvaluator",
    "StrategyRunContext",
    "TrainTestSlice",
    "Transformer",
    "VariableSpec",
    "WalkForwardPlan",
    "apply_stock_split_adjustments",
    "build_daily_eod_panels",
    "build_residual_regime_target",
    "build_split_adjustment_factors",
    "run_experiment",
]