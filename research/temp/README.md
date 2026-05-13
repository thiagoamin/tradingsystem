# Research

## Goal

Provide a fast experimentation sandbox for strategy ideas and risk/utility modeling without changing core engine code.

The main focus here is comparing:

1. Different signal models (`Dip`, `Momentum`, `MeanReversion`).
2. Different utility functions and risk-aversion settings.
3. Resulting trade behavior and portfolio performance.

## Implemented

- `backtest_lab.py`
  - Lightweight backtest harness.
  - Per-symbol and true multi-asset (shared-cash) portfolio simulation.
  - Strategy abstraction and performance metrics (return, drawdown, Sharpe).
  - Experiment matrix config for multi-symbol runs and portfolio-level comparisons.
- `signals.py`
  - Signal framework and three concrete signals.
- `utility_functions.py`
  - Compatibility wrapper that re-exports shared utility classes from
    `allocation/utility_functions.py`.

## TODO

- Parameter sweep automation and result persistence.
- Plotting/visual reports for equity curves and drawdowns.
- Walk-forward / out-of-sample evaluation tooling.
- Explicit transaction-cost and slippage modeling in research runs.
- Shared signal interfaces between research and production strategy modules.
