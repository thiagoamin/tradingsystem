"""Processing utilities for research workflows."""

from research.tools.processing.quote_variables import (
    DEFAULT_QUOTE_VARIABLES,
    QuoteVariable,
    QuoteVariablePanels,
    build_quote_variables,
)
from research.tools.processing.residual_features import build_residual_forecast_features
from research.tools.processing.returns_builder import build_returns
from research.tools.processing.returns_config import ReturnsConfig
from research.tools.processing.trade_variables import (
    DEFAULT_TRADE_VARIABLES,
    TradeVariable,
    TradeVariablePanels,
    build_trade_variables,
)

__all__ = [
    "DEFAULT_QUOTE_VARIABLES",
    "DEFAULT_TRADE_VARIABLES",
    "QuoteVariable",
    "QuoteVariablePanels",
    "ReturnsConfig",
    "TradeVariable",
    "TradeVariablePanels",
    "build_residual_forecast_features",
    "build_quote_variables",
    "build_returns",
    "build_trade_variables",
]
