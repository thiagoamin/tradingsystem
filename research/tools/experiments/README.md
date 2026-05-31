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
- `FoldRecord`, `ExperimentRunManifest` -- realized experiment audit records.
  These are not contracts and do not run anything; they serialize the actual
  train/validation/test windows, retrain decisions, selected parameters,
  metrics, and artifact paths from a completed run.

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

## Run manifests

Use a manifest when you want to record what actually happened after an
experiment finishes:

```python
from research.tools.experiments import ExperimentRunManifest, FoldRecord
from research.tools.splits import WalkForwardSplitter

slices = WalkForwardSplitter(
    train_window_days=504,
    test_window_days=63,
    step_days=63,
    retrain_every_n_folds=1,
).build_slices(start_date, end_date)

folds = tuple(
    FoldRecord.from_slice(
        slc,
        selected_params={"candidate": "mr_p035_s150"},
        metrics={"sharpe": 0.59},
        artifacts={"weights": f"fold_{slc.fold_id:03d}/test_target_weights.csv"},
    )
    for slc in slices
)

manifest = ExperimentRunManifest(
    experiment_name="hybrid_residual_nested_tuning",
    contract_name="hybrid_residual_nested_tuning_contract",
    run_id="20260530_120000",
    folds=folds,
    artifacts={"summary": "summary.csv"},
)
manifest.write_json("run_manifest.json")
```
