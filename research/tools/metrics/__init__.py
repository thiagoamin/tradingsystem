"""Composable metrics for backtest evaluation.

Each ``Metric`` consumes a ``MetricContext`` and returns either a scalar (the
common case) or a dict of named scalars (when the metric is naturally
multi-valued, e.g. per-sector or per-mode attribution). ``MetricSet`` runs a
list of metrics against the same context and flattens the result, prefixing
multi-value outputs with the metric's name so column names stay unambiguous.

The existing evaluators in ``research.tools.evaluation`` are still the source
of truth for the underlying formulas; the metrics here are thin adapters so
any experiment can declare its tracked metrics as a list rather than calling
evaluators imperatively.
"""

from research.tools.metrics.base import Metric, MetricContext, MetricSet
from research.tools.metrics.headline import (
    ActiveRate,
    AvgGrossExposure,
    BarVolatility,
    CumulativeReturn,
    HeadlineMetrics,
    HitRate,
    MaxDrawdown,
    MeanBarReturn,
    PositionChangeCount,
    Sharpe,
    Turnover,
)
from research.tools.metrics.attribution import ModeAttribution, PerSectorAttribution

__all__ = [
    "ActiveRate",
    "AvgGrossExposure",
    "BarVolatility",
    "CumulativeReturn",
    "HeadlineMetrics",
    "HitRate",
    "MaxDrawdown",
    "MeanBarReturn",
    "Metric",
    "MetricContext",
    "MetricSet",
    "ModeAttribution",
    "PerSectorAttribution",
    "PositionChangeCount",
    "Sharpe",
    "Turnover",
]
