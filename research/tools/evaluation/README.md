# Evaluation

This package is for post-backtest assessment.

An evaluator takes realized backtest outputs and maps them into summary diagnostics:

$$
\text{realized pnl path} \mapsto \text{performance metrics}
$$

Examples:

- pnl series $\rightarrow$ total return, Sharpe, drawdown
- trade history $\rightarrow$ hit rate, average trade return, turnover

No concrete evaluator has been implemented yet. The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/base.py)

First concrete implementation:

- [basic.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/basic.py)
  - `BasicStrategyEvaluator`
  - computes cumulative return, mean bar return, bar volatility, Sharpe, max drawdown, hit rate, and turnover
