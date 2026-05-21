# Backtest

This package is for simulation logic.

A backtest engine takes strategy outputs, aligns them with realized returns, and produces realized outcomes such as pnl:

$$
(\text{positions}, \text{realized returns}) \mapsto \text{pnl path}
$$

Examples:

- signal panel $\rightarrow$ lagged positions $\rightarrow$ realized pnl
- target weights + realized returns $\rightarrow$ strategy return series

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/backtest/base.py)

Concrete implementation:

- [simple_backtest.py](/Users/thiagoamin/Desktop/trading_system/research/tools/backtest/simple_backtest.py)
  - `SimpleBacktestEngine`
  - applies a position lag and optionally normalizes gross exposure before computing pnl

## Simple PnL Convention

For positions $q_i(t)$ and realized returns $r_i(t)$, the simple engine applies `position_lag=L`:

$$
\tilde{q}_i(t) = q_i(t-L)
$$

If gross normalization is enabled:

$$
w_i(t) =
\frac{\tilde{q}_i(t)}
{\sum_j |\tilde{q}_j(t)|}
$$

when gross exposure is nonzero, otherwise all weights are zero.

Per-symbol PnL is:

$$
\text{pnl}_i(t) = w_i(t)r_i(t)
$$

The default `position_lag=1` means a signal generated at bar $t$ is first applied to the next realized return. This is the no-lookahead convention used by the residual experiments.
