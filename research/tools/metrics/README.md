# Metrics

Composable, declarative metrics for backtest evaluation.

An experiment declares the metrics it tracks as a list, and the runner
applies them uniformly. New metrics are added by subclassing ``Metric``;
nothing about the runner changes.

## Implementation map

- [base.py](base.py)
  - `MetricContext` -- payload (pnl + optional weights, modes, asset PnL,
    factor betas, returns, symbol groups, annualization factor).
  - `Metric` -- ABC: ``name``, ``compute(ctx) -> float | dict[str, float]``.
  - `MetricSet` -- runs a tuple of metrics against the same context and
    flattens multi-value results (``"<name>.<subkey>"``).
- [headline.py](headline.py)
  - Single-scalar metrics matching ``BasicStrategyEvaluator``:
    `CumulativeReturn`, `MeanBarReturn`, `BarVolatility`, `Sharpe`,
    `MaxDrawdown`, `HitRate`, `Turnover`, `AvgGrossExposure`, `ActiveRate`,
    `PositionChangeCount`.
  - `HeadlineMetrics()` returns the ten-tuple as a one-liner.
- [attribution.py](attribution.py)
  - `ModeAttribution` -- annualised Sharpe per per-stock mode label
    (``mean_reversion``, ``trend``, ``inverse_trend``, ``flat``).
  - `PerSectorAttribution(cost_rate=...)` -- net PnL grouped by
    ``ctx.symbol_groups``; cost rate must match the engine you ran.

## Typical usage

```python
from research.tools.metrics import (
    HeadlineMetrics,
    MetricContext,
    MetricSet,
    ModeAttribution,
    PerSectorAttribution,
)

ms = MetricSet(
    metrics=HeadlineMetrics()
    + (
        ModeAttribution(),
        PerSectorAttribution(cost_rate=0.0005),
    ),
)
ctx = MetricContext(
    pnl=portfolio_pnl["net_pnl"],
    weights=target_weights,
    asset_pnl=asset_pnl,
    modes=modes,
    symbol_groups={"XLK": ("AAPL", "MSFT", ...), "XLF": (...)},
    annualization_factor=252,
)
result = ms.compute_all(ctx)
# {"sharpe": 0.5938, "cum_return": 0.0257, ..., "mode_attribution.inverse_trend": 0.22, ...}
```

## Relationship to ``research.tools.evaluation``

The evaluators in ``research.tools.evaluation`` are the source of truth for
the underlying formulas (and for hedge-pnl-allocated mode attribution, which
is more elaborate than the simple stock-side ``ModeAttribution`` here). The
metrics in this package are thin adapters so an experiment can declare
*which* numbers to track without calling evaluators imperatively. Both
remain available; pick the one that fits the use site.

## Where to extend

- Risk: `SortinoRatio`, `Calmar`, downside vol.
- Cost: `TransactionCostRatio` (total cost / total gross PnL).
- Exposure: `FactorExposure(factor)` reading from `exposure_diagnostics`.
- Stability: `WorstFoldSharpe`, `FoldSharpeStd` (require fold-segmented PnL).

Subclass ``Metric``, return a scalar or dict. The set picks it up.
