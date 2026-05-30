from __future__ import annotations

"""Standard portfolio-level metrics.

Each one wraps the corresponding output of ``BasicStrategyEvaluator``; using
them through ``MetricSet`` lets experiments declare exactly which numbers to
report instead of always receiving the full evaluator dict.
"""

from dataclasses import dataclass

import numpy as np

from research.tools.metrics.base import Metric, MetricContext


@dataclass(frozen=True)
class CumulativeReturn(Metric):
    @property
    def name(self) -> str:
        return "cum_return"

    def compute(self, ctx: MetricContext) -> float:
        wealth = (1.0 + ctx.pnl.fillna(0.0)).cumprod()
        return float(wealth.iloc[-1] - 1.0) if not wealth.empty else float("nan")


@dataclass(frozen=True)
class MeanBarReturn(Metric):
    @property
    def name(self) -> str:
        return "mean_bar_return"

    def compute(self, ctx: MetricContext) -> float:
        return float(ctx.pnl.fillna(0.0).mean())


@dataclass(frozen=True)
class BarVolatility(Metric):
    @property
    def name(self) -> str:
        return "bar_vol"

    def compute(self, ctx: MetricContext) -> float:
        return float(ctx.pnl.fillna(0.0).std())


@dataclass(frozen=True)
class Sharpe(Metric):
    """Annualised Sharpe using ``ctx.annualization_factor``."""

    @property
    def name(self) -> str:
        return "sharpe"

    def compute(self, ctx: MetricContext) -> float:
        pnl = ctx.pnl.fillna(0.0)
        vol = float(pnl.std())
        if vol == 0.0:
            return float("nan")
        sharpe = float(pnl.mean()) / vol
        return sharpe * float(np.sqrt(ctx.annualization_factor))


@dataclass(frozen=True)
class MaxDrawdown(Metric):
    @property
    def name(self) -> str:
        return "max_drawdown"

    def compute(self, ctx: MetricContext) -> float:
        wealth = (1.0 + ctx.pnl.fillna(0.0)).cumprod()
        running_peak = wealth.cummax()
        drawdown = wealth / running_peak - 1.0
        return float(drawdown.min()) if not drawdown.empty else float("nan")


@dataclass(frozen=True)
class HitRate(Metric):
    @property
    def name(self) -> str:
        return "hit_rate"

    def compute(self, ctx: MetricContext) -> float:
        pnl = ctx.pnl.fillna(0.0)
        return float((pnl > 0.0).mean()) if not pnl.empty else float("nan")


@dataclass(frozen=True)
class Turnover(Metric):
    """Average single-day turnover; requires ``weights``."""

    @property
    def name(self) -> str:
        return "turnover"

    def compute(self, ctx: MetricContext) -> float:
        if ctx.weights is None:
            return float("nan")
        return float(ctx.weights.diff().abs().sum(axis=1).mean())


@dataclass(frozen=True)
class AvgGrossExposure(Metric):
    @property
    def name(self) -> str:
        return "avg_gross_exposure"

    def compute(self, ctx: MetricContext) -> float:
        if ctx.weights is None:
            return float("nan")
        return float(ctx.weights.abs().sum(axis=1).mean())


@dataclass(frozen=True)
class ActiveRate(Metric):
    @property
    def name(self) -> str:
        return "active_rate"

    def compute(self, ctx: MetricContext) -> float:
        if ctx.weights is None:
            return float("nan")
        gross = ctx.weights.abs().sum(axis=1)
        return float((gross > 0.0).mean())


@dataclass(frozen=True)
class PositionChangeCount(Metric):
    @property
    def name(self) -> str:
        return "position_change_count"

    def compute(self, ctx: MetricContext) -> float:
        if ctx.weights is None:
            return float("nan")
        return float(ctx.weights.diff().abs().sum(axis=1).sum())


def HeadlineMetrics() -> tuple[Metric, ...]:
    """Standard 10-metric bundle equivalent to ``BasicStrategyEvaluator.evaluate``.

    Returned as a tuple so it can be passed straight to ``MetricSet``.
    """
    return (
        CumulativeReturn(),
        MeanBarReturn(),
        BarVolatility(),
        Sharpe(),
        MaxDrawdown(),
        HitRate(),
        Turnover(),
        AvgGrossExposure(),
        ActiveRate(),
        PositionChangeCount(),
    )
