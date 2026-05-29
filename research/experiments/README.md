# Experiments

Concrete research runs that compose the reusable tools in
[`research/tools/`](../tools/). Each experiment script is allowed to:

- choose universes, date ranges, and horizons
- declare a train/test splitter (rolling, expanding, single, nested-CV)
- pick a data source (cached, ThetaData, layered)
- write output tables and diagnostics
- compare alternative transformers, strategies, backtests, and evaluators

Anything reusable belongs in `research/tools/`, not here. Output mirrors the
experiment path under [`research/experiment_outputs/`](../experiment_outputs/)
so each script's results live where you expect.

## Layout

```
research/experiments/
├── README.md                 (this file)
├── paper_replications/
│   └── avellaneda_lee_2008/
│       ├── theory/           tex + pdf source for the spec + extension
│       └── one_day/          daily-horizon implementation
│           ├── README.md     run guide + result summary
│           ├── REFERENCE_STRATEGY.md (TBD)
│           └── ...
└── endogenous_horizon/
    └── theory/               core theory (no experiment yet)
```

## Active experiment lines

### Daily Avellaneda--Lee residual statistical arbitrage

Everything daily lives under
[`paper_replications/avellaneda_lee_2008/one_day/`](paper_replications/avellaneda_lee_2008/one_day/README.md).
That folder's README is the canonical run guide and result summary. Headline:

- Best OOS Sharpe: **0.594** (17-fold nested walk-forward, 12-stock tech
  universe, hybrid mean-reversion + inverse-trend regime classifier,
  per-stock residual-vol-targeted sizing).
- See
  [`paper_replications/avellaneda_lee_2008/one_day/README.md`](paper_replications/avellaneda_lee_2008/one_day/README.md)
  for the full inventory, pipeline diagram, and results tour.

### Endogenous horizon

Theory only, no implementation yet. See
[`endogenous_horizon/README.md`](endogenous_horizon/README.md).

## How an experiment ties the tools together

Every active experiment follows the same five-step shape, parameterised at
each step by the corresponding `research/tools/` abstraction:

| Step | Tool package | Default for the daily experiments |
|---|---|---|
| 1. Load panels | `research/tools/data` | `LayeredPanelSource([CachedPanelSource, ThetaPanelSource])` |
| 2. Build residuals + state | `research/tools/transformer` | `RollingFactorResidualizationModel` + `ResidualStateTransformer` |
| 3. Walk-forward partition | `research/tools/splits` | `WalkForwardSplitter` (or `NestedWalkForwardSplitter` for tuning) |
| 4. Strategy + backtest | `research/tools/strategy` + `research/tools/backtest` | `HybridResidualStrategy` + `FactorHedgedDailyBacktestEngine` |
| 5. Score | `research/tools/evaluation` + `research/tools/metrics` | `BasicStrategyEvaluator` + `HybridModeAttributionEvaluator` |

Swapping any single step is a one-line config change.

## Running

ThetaData fetches need `creds.txt` in the working directory:

```bash
cd /Users/thiagoamin/Desktop/trading_system
ln -sf research/fetchers/thetadata/creds.txt creds.txt
```

Each script supports the standard module invocation, e.g.:

```bash
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_nested_tuning
```

Outputs go to the mirrored path under `research/experiment_outputs/`.
