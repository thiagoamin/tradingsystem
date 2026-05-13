# Strategy

This package is for trading decision logic.

A strategy takes transformed data, forecasts, or both, and maps them into signals or positions:

$$
\text{model outputs} \mapsto \text{signals or positions}
$$

Examples:

- residual panel $\rightarrow$ mean-reversion signal
- alpha forecast $\rightarrow$ target position
- multiple model outputs $\rightarrow$ combined portfolio weights

This sits after transformation or prediction, but before backtesting:

$$
\text{model outputs} \rightarrow \text{signals or positions} \rightarrow \text{backtest}
$$

No concrete strategy has been implemented yet. The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/base.py)

First concrete implementation:

- [residual_zscore.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/residual_zscore.py)
  - `ResidualZScoreStrategy`
  - builds long/short/flat positions from rolling residual z-scores
