# Backtest

This package is for simulation logic.

A backtest engine takes strategy outputs, aligns them with realized returns, and produces realized outcomes such as pnl:

$$
(\text{positions}, \text{realized returns}) \mapsto \text{pnl path}
$$

Examples:

- signal panel $\rightarrow$ lagged positions $\rightarrow$ realized pnl
- target weights + realized returns $\rightarrow$ strategy return series

No concrete backtest engine has been implemented yet. The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/backtest/base.py)

First concrete implementation:

- [simple_backtest.py](/Users/thiagoamin/Desktop/trading_system/research/tools/backtest/simple_backtest.py)
  - `SimpleBacktestEngine`
  - applies a position lag and optionally normalizes gross exposure before computing pnl
