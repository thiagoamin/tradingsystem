"""Pluggable data sources that all produce ``DailyEodPanels``.

Experiments depend on this package's ``DataSource`` ABC, not on the underlying
fetcher. Swapping cached for live data, or merging multiple sources, is a
matter of constructing a different ``DataSource`` -- not editing experiment
code.
"""

from research.tools.data.base import (
    DataSource,
    PanelRequest,
    UniverseSpec,
)
from research.tools.data.cached import CachedPanelSource
from research.tools.data.layered import LayeredPanelSource
from research.tools.data.thetadata import ThetaPanelSource

__all__ = [
    "CachedPanelSource",
    "DataSource",
    "LayeredPanelSource",
    "PanelRequest",
    "ThetaPanelSource",
    "UniverseSpec",
]
