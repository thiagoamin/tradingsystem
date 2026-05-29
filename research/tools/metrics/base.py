from __future__ import annotations

"""``Metric`` ABC, ``MetricContext`` payload, and ``MetricSet`` aggregator."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class MetricContext:
    """Inputs a metric can consume.

    Only ``pnl`` is required. Everything else is optional so a metric can be
    computed against partial backtest output (e.g. attribution metrics need
    ``modes``, exposure metrics need ``weights``).

    Attributes:
        pnl: Net per-bar portfolio PnL series, indexed by date.
        weights: Per-asset target weight panel.
        modes: Per-stock mode labels (``"mean_reversion"``, ``"trend"``,
            ``"inverse_trend"``, ``"flat"``, ...).
        asset_pnl: Per-asset realized PnL panel.
        returns: Per-asset realized return panel.
        factor_betas: Per-factor beta panel mapping factor name to panel.
        exposure_diagnostics: Daily exposure diagnostics from the engine.
        symbol_groups: Mapping group-label -> list of stock symbols. Used by
            ``PerSectorAttribution`` and similar group-wise metrics.
        annualization_factor: Bars per year (252 for daily, 252*78 for 5min, etc).
    """

    pnl: pd.Series
    weights: pd.DataFrame | None = None
    modes: pd.DataFrame | None = None
    asset_pnl: pd.DataFrame | None = None
    returns: pd.DataFrame | None = None
    factor_betas: dict[str, pd.DataFrame] | None = None
    exposure_diagnostics: pd.DataFrame | None = None
    symbol_groups: dict[str, tuple[str, ...]] | None = None
    annualization_factor: float = 252.0


class Metric(ABC):
    """One named scalar (or dict-of-scalars) computed from a ``MetricContext``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short snake_case identifier used as the column key."""

    @abstractmethod
    def compute(self, ctx: MetricContext) -> float | dict[str, float]:
        """Return the metric's value(s).

        If the value is a dict, ``MetricSet`` flattens its entries by joining
        the metric name with each sub-key as ``f"{name}.{subkey}"``.
        """


@dataclass(frozen=True)
class MetricSet:
    """Run a list of metrics against the same context."""

    metrics: tuple[Metric, ...] = field(default_factory=tuple)

    def compute_all(self, ctx: MetricContext) -> dict[str, float]:
        out: dict[str, float] = {}
        for metric in self.metrics:
            value = metric.compute(ctx)
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    out[f"{metric.name}.{subkey}"] = float(subval)
            else:
                out[metric.name] = float(value)
        return out
