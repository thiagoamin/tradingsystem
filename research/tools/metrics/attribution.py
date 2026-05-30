from __future__ import annotations

"""Attribution metrics: by mode label, by symbol group (sector)."""

from dataclasses import dataclass

import numpy as np

from research.tools.metrics.base import Metric, MetricContext


@dataclass(frozen=True)
class ModeAttribution(Metric):
    """Per-mode annualised Sharpe.

    Requires ``modes`` and ``asset_pnl`` on the context. PnL is attributed to
    the contemporaneous mode label of each stock cell. Returns a dict keyed by
    mode name; ``MetricSet`` flattens to ``mode_attribution.mean_reversion``,
    ``mode_attribution.trend``, etc.
    """

    @property
    def name(self) -> str:
        return "mode_attribution"

    def compute(self, ctx: MetricContext) -> dict[str, float]:
        if ctx.modes is None or ctx.asset_pnl is None:
            return {}
        modes = ctx.modes
        # asset_pnl includes both stocks and factor ETFs; only stock columns
        # share the modes panel's columns.
        stock_cols = [c for c in modes.columns if c in ctx.asset_pnl.columns]
        if not stock_cols:
            return {}
        stock_pnl = ctx.asset_pnl[stock_cols]
        modes = modes[stock_cols]
        out: dict[str, float] = {}
        for mode in sorted(modes.stack().unique()):
            mask = modes.eq(mode)
            if not bool(mask.any().any()):
                continue
            daily = stock_pnl.where(mask, 0.0).sum(axis=1)
            vol = float(daily.std())
            if vol == 0.0:
                out[mode] = float("nan")
            else:
                out[mode] = float(daily.mean()) / vol * float(np.sqrt(ctx.annualization_factor))
        return out


@dataclass(frozen=True)
class PerSectorAttribution(Metric):
    """Per-symbol-group cumulative net PnL.

    Requires ``asset_pnl``, ``weights``, and ``symbol_groups``. Net PnL per
    group is its members' asset PnL minus an equal-cost-rate transaction-cost
    estimate based on its members' turnover.

    The cost rate is read from the supplied ``cost_rate`` (in fraction units,
    e.g. ``0.0005`` for 5 bps). It deliberately does not introspect the engine,
    so the same metric works across any backtest engine; just pass the same
    ``cost_rate`` you configured the engine with.
    """

    cost_rate: float = 0.0

    @property
    def name(self) -> str:
        return "per_sector_net"

    def compute(self, ctx: MetricContext) -> dict[str, float]:
        if ctx.asset_pnl is None or ctx.weights is None or ctx.symbol_groups is None:
            return {}
        turnover = ctx.weights.diff().fillna(ctx.weights).abs()
        out: dict[str, float] = {}
        for group, members in ctx.symbol_groups.items():
            present = [m for m in members if m in ctx.asset_pnl.columns]
            if not present:
                out[group] = float("nan")
                continue
            gross = float(ctx.asset_pnl[present].sum().sum())
            cost = float(turnover[present].sum().sum()) * float(self.cost_rate)
            out[group] = gross - cost
        return out
