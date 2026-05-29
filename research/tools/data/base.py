from __future__ import annotations

"""``DataSource`` ABC -- all return ``DailyEodPanels`` for a fixed universe."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from research.tools.processing import DailyEodPanels, StockSplit


@dataclass(frozen=True)
class UniverseSpec:
    """The minimum a ``DataSource`` needs to assemble a panel.

    Attributes:
        stocks: Modeled stock symbols. Order is preserved in panel columns.
        factor_etfs: ETF symbols supplying factor returns. Disjoint from ``stocks``.
        split_events: Verified stock splits applied to raw closes before
            returns are computed. The data source is responsible for filtering
            to events whose symbol appears in this universe.
    """

    stocks: tuple[str, ...]
    factor_etfs: tuple[str, ...]
    split_events: tuple[StockSplit, ...] = ()

    def __post_init__(self) -> None:
        overlap = set(self.stocks) & set(self.factor_etfs)
        if overlap:
            raise ValueError(f"stocks and factor_etfs must be disjoint; overlap: {sorted(overlap)}")
        if not self.stocks:
            raise ValueError("stocks must be non-empty")

    @property
    def symbols(self) -> tuple[str, ...]:
        """All symbols the source must produce, stocks first then factor ETFs."""
        return tuple(self.stocks) + tuple(self.factor_etfs)

    @property
    def applicable_splits(self) -> tuple[StockSplit, ...]:
        """Splits filtered to symbols present in this universe."""
        symbols = set(self.symbols)
        return tuple(event for event in self.split_events if event.symbol in symbols)


@dataclass(frozen=True)
class PanelRequest:
    """One concrete data request: universe + date window."""

    universe: UniverseSpec
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError(f"start_date {self.start_date} must precede end_date {self.end_date}")


class DataSource(ABC):
    """Produces ``DailyEodPanels`` for a ``PanelRequest``.

    Implementations may pull from a local cache, a remote provider, a merge of
    both, or synthetic generators. All return the same structured panel so
    downstream pipeline code is data-source-agnostic.
    """

    @abstractmethod
    def get_panels(self, request: PanelRequest) -> DailyEodPanels:
        """Return panels for the given universe and date range.

        Raises:
            FileNotFoundError: For cached-only sources missing required data.
            ValueError: For malformed responses (missing symbols, etc).
        """

    def universe_from_lists(
        self,
        stocks: Sequence[str],
        factor_etfs: Sequence[str],
        split_events: Sequence[StockSplit] = (),
    ) -> UniverseSpec:
        """Convenience constructor preserving order and tupleizing inputs."""
        return UniverseSpec(
            stocks=tuple(stocks),
            factor_etfs=tuple(factor_etfs),
            split_events=tuple(split_events),
        )
