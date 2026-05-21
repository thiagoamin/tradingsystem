from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

QuoteVariablePanels = dict[str, pd.DataFrame]
TradeVariablePanels = dict[str, pd.DataFrame]


def build_residual_forecast_features(
    residuals: pd.DataFrame,
    quote_variables: QuoteVariablePanels,
    variable_names: Sequence[str] = ("spread_bps", "imbalance", "microprice_pressure"),
    residual_window: int = 8,
    trade_variables: TradeVariablePanels | None = None,
) -> pd.DataFrame:
    """Build per-symbol features used to forecast next-bar residual returns.

    Output columns are a MultiIndex of ``(symbol, feature)``. All features are
    known at timestamp ``t`` and are intended to predict residual return at
    ``t + 1``.
    """
    if residuals.empty:
        raise ValueError("residuals must be non-empty")
    if residual_window < 2:
        raise ValueError("residual_window must be >= 2")
    market_variables = dict(quote_variables)
    if trade_variables is not None:
        market_variables.update(trade_variables)

    blocks: list[pd.DataFrame] = []
    for symbol in residuals.columns:
        symbol_features = pd.DataFrame(index=residuals.index)
        series = residuals[symbol]
        symbol_features["residual"] = series
        symbol_features["residual_mean"] = series.rolling(residual_window, min_periods=residual_window).mean()
        symbol_features["residual_vol"] = series.rolling(residual_window, min_periods=residual_window).std()
        for name in variable_names:
            if name not in market_variables:
                raise ValueError(f"market variables must include '{name}'")
            symbol_features[name] = market_variables[name].reindex(index=residuals.index, columns=residuals.columns)[symbol]
        symbol_features.columns = pd.MultiIndex.from_product([[symbol], symbol_features.columns])
        blocks.append(symbol_features)
    out = pd.concat(blocks, axis=1)
    out.index = residuals.index
    return out
