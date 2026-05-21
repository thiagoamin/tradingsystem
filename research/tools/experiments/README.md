# Experiments Core

This package provides reusable experiment orchestration for strategy research.

It standardizes:

- split planning (`single_split`, `walk_forward`)
- retrain cadence (`retrain_every_n_folds`)
- horizon loops
- artifact writing
- summary table generation

The runner is callback-based so each experiment can plug in its own:

- return builder
- transformer fit/transform
- strategy position generation
- backtest
- evaluation

Use thin scripts under `research/experiments/` to define concrete implementations and defaults.
