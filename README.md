# Trading System

This repository is building a modular algorithmic trading platform with two main execution modes:

- **Backtesting** on historical data.
- **Paper trading** on Interactive Brokers (IBKR).

The core architecture is:

1. Ingest market data.
2. Compute features/indicators.
3. Generate signal events.
4. Translate signals into target position actions.
5. Apply risk controls.
6. Execute orders and update the portfolio.

## Folder Guide

- `engine/` - core trading runtime and orchestration.
- `data/` - data feed wrappers and feature pipeline.
- `research/fetchers/` - provider abstraction and data models.
- `research/` - experimental backtesting and signal/utility exploration.
- `tests/` - unit tests for core modules.
