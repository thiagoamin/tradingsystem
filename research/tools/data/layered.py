from __future__ import annotations

"""Stack of ``DataSource``s: first hit wins. Useful for cache-then-fetch."""

from collections.abc import Iterable

from research.tools.data.base import DataSource, PanelRequest
from research.tools.processing import DailyEodPanels


class LayeredPanelSource(DataSource):
    """Try each source in order until one succeeds.

    Typical pattern::

        source = LayeredPanelSource([
            CachedPanelSource(cache_root),
            ThetaPanelSource(cache_root=cache_root),
        ])

    A ``FileNotFoundError`` from the cached layer falls through to the next
    source; any other exception type is propagated unchanged because it likely
    represents a programming error rather than a missing cache.
    """

    def __init__(self, sources: Iterable[DataSource]):
        self._sources = list(sources)
        if not self._sources:
            raise ValueError("LayeredPanelSource requires at least one underlying source")

    def get_panels(self, request: PanelRequest) -> DailyEodPanels:
        last_error: FileNotFoundError | None = None
        for source in self._sources:
            try:
                return source.get_panels(request)
            except FileNotFoundError as error:
                last_error = error
                continue
        assert last_error is not None
        raise last_error
