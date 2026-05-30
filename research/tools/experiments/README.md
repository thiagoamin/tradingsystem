# Experiments Core (legacy)

Original callback-based experiment runner. Predates the
[`splits/`](../splits/), [`data/`](../data/), and [`metrics/`](../metrics/)
packages and remains importable so existing experiment scripts do not need
to be touched.

## What this package still provides

- `WalkForwardPlan`, `TrainTestSlice`, `business_days` -- same shape as
  `WalkForwardSplitter`, `Slice`, `business_days` in
  [`research/tools/splits/`](../splits/).
- `ExperimentConfig`, `Mode`, `run_experiment(cfg, ...)` -- the original
  callback-based runner that takes seven callables (build returns, fit
  transformer, transform, generate positions, backtest, evaluate, optional
  state writer).

## When to use what

- Use [`research/tools/splits/`](../splits/) for new code -- it is the
  recommended path for rolling, expanding, single, and nested-CV partitions.
- Use [`research/tools/data/`](../data/) instead of writing a custom
  `build_returns` callable.
- Use [`research/tools/metrics/`](../metrics/) instead of writing a custom
  `evaluate` callable.
- The legacy `run_experiment` is still appropriate for one-off experiments
  whose pipeline does not fit a clean transformer/predictor/strategy shape.
  The big-grid hybrid experiments under
  [`research/experiments/paper_replications/avellaneda_lee_2008/one_day/`](../../experiments/paper_replications/avellaneda_lee_2008/one_day/)
  have outgrown the callback runner and use their own walk-forward loops.

A future cleanup pass will fold `WalkForwardPlan` / `TrainTestSlice` into the
splits package as direct re-exports; until then both work.
