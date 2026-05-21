# Evaluation

This package is for post-backtest assessment.

An evaluator takes realized backtest outputs and maps them into summary diagnostics:

$$
\text{realized pnl path} \mapsto \text{performance metrics}
$$

Examples:

- pnl series $\rightarrow$ total return, Sharpe, drawdown
- trade history $\rightarrow$ hit rate, average trade return, turnover

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/base.py)

Concrete implementation:

- [basic.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/basic.py)
  - `BasicStrategyEvaluator`
  - computes cumulative return, mean bar return, bar volatility, Sharpe, max drawdown, hit rate, turnover, average gross exposure, active rate, and position-change count

## Current Metrics

For portfolio PnL $p(t)=\sum_i \text{pnl}_i(t)$:

$$
\text{wealth}(t)=\prod_{u \le t}(1+p(u))
$$

$$
\text{cum\_return}=\text{wealth}(T)-1
$$

$$
\text{sharpe}=\frac{\text{mean}(p)}{\text{std}(p)}
$$

This Sharpe is per-bar unless an `annualization_factor` is provided.

With positions $q_i(t)$, turnover is:

$$
\text{turnover} = \text{mean}_t \sum_i |q_i(t)-q_i(t-1)|
$$

Average gross exposure is:

$$
\text{avg\_gross\_exposure} = \text{mean}_t \sum_i |q_i(t)|
$$

Active rate is the fraction of bars with nonzero gross exposure.
