# Tools

Framework layer for the research pipeline. Every concrete experiment under
[`../experiments/`](../experiments/) composes pieces from here. Each
sub-package has its own README with the maths and the implementation map.

## The pipeline

```
DataSource           -> DailyEodPanels
        v
Transformer / Predictor / Strategy   (research signal stack)
        v
BacktestEngine       -> portfolio_pnl + target_weights + asset_pnl
        v
MetricSet            -> headline metrics
                        + attribution metrics
```

Each step is selected from a sub-package below; swapping any step is a
constructor argument, not an edit.

## Sub-packages

| Package | Role | README |
|---|---|---|
| [`data/`](data/) | `DataSource` ABC. `CachedPanelSource`, `ThetaPanelSource`, `LayeredPanelSource`. Returns `DailyEodPanels`. | [README](data/README.md) |
| [`processing/`](processing/) | Daily EOD record -> `DailyEodPanels`. Stock-split adjustment. | [README](processing/README.md) |
| [`transformer/`](transformer/) | Panel -> panel. Residualization, residual-state features, OU estimation. | [README](transformer/README.md) |
| [`predictor/`](predictor/) | Panel features -> `P(label)`. Per-stock logistic regime classifier. | [README](predictor/README.md) |
| [`strategy/`](strategy/) | Panel signals -> stock-side positions. OU-s-score, hybrid residual. | [README](strategy/README.md) |
| [`backtest/`](backtest/) | Positions + returns -> portfolio PnL. Factor-hedged daily engine with optional vol targeting. | [README](backtest/README.md) |
| [`splits/`](splits/) | Train/test partitioner. Walk-forward, nested walk-forward, single, expanding. | [README](splits/README.md) |
| [`metrics/`](metrics/) | Composable `Metric` + `MetricSet`. Wraps the underlying evaluators. | [README](metrics/README.md) |
| [`evaluation/`](evaluation/) | Underlying evaluators: headline + hybrid mode attribution. | [README](evaluation/README.md) |
| [`experiments/`](experiments/) | Legacy callback-based runner. Predates `splits/` + `metrics/`; kept for back-compat. | [README](experiments/README.md) |
| [`live/`](live/) | Event-driven runtime for live and paper trading. Sibling to the batch backtest engine. | [README](live/README.md) |
| [`transformer/mean_reversion/`](transformer/mean_reversion/) | `OUEstimator`, paper-style assigned-ETF OU score model. | [README](transformer/mean_reversion/README.md) |
| [`transformer/residual_state/`](transformer/residual_state/) | Causal state features (level, trend, displacement, OU s-score, volume). | [README](transformer/residual_state/README.md) |
| [`transformer/residualization/`](transformer/residualization/) | Rolling-OLS factor exposure paths and residual returns. | [README](transformer/residualization/README.md) |

## Extending

The system is intended to be extended by adding new implementations of the
existing ABCs, not by editing the runner. Most common extensions:

- **New data source** -- subclass `DataSource`, implement `get_panels`.
- **New split scheme** -- subclass `Splitter`, return `list[Slice]`.
- **New metric** -- subclass `Metric`, return scalar or dict of scalars.
- **New transformer/predictor/strategy** -- subclass the corresponding ABC and
  follow the panel-shape contract documented in the relevant README.

Concrete experiment scripts under [`../experiments/`](../experiments/)
remain thin: they pick which pieces to use, declare config, and call the
runner.
