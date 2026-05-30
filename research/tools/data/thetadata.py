from __future__ import annotations

"""Data source that fetches EOD records from ThetaData and (optionally)
materializes the cache used by ``CachedPanelSource``.
"""

from dataclasses import dataclass
from pathlib import Path

from research.fetchers.thetadata import ThetaDataEodIngestor
from research.tools.data.base import DataSource, PanelRequest
from research.tools.processing import DailyEodPanels, build_daily_eod_panels


@dataclass(frozen=True)
class ThetaIngestResult:
    """Companion to the panel for callers who want to inspect raw paths."""

    panels: DailyEodPanels
    raw_paths: dict[str, Path]


class ThetaPanelSource(DataSource):
    """Fetch from ThetaData (using the per-symbol global cache layer in
    ``research/fetchers/thetadata/theta_storage.py``).

    Optionally writes the canonical ``eod_raw_close_panel.csv`` +
    ``eod_raw_volume_panel.csv`` to ``cache_root`` so a subsequent
    ``CachedPanelSource(cache_root)`` can reuse the result without a network
    call. This keeps a clean separation: ThetaData is the *source of truth*,
    the cached panel is its on-disk projection.
    """

    def __init__(
        self,
        cache_root: Path | None = None,
        *,
        dataframe_type: str = "pandas",
        reuse_cache: bool = True,
    ):
        """Args:
            cache_root: If set, ``get_panels`` writes the raw close/volume
                panels here after fetching. Pass the same directory to a
                ``CachedPanelSource`` to skip future fetches.
            dataframe_type: Passed through to ``ThetaDataEodIngestor``.
            reuse_cache: Whether the underlying ingestor should reuse the
                per-symbol global cache in ``ThetaDataStorage``.
        """
        self._cache_root = Path(cache_root) if cache_root is not None else None
        self._dataframe_type = dataframe_type
        self._reuse_cache = reuse_cache

    @property
    def cache_root(self) -> Path | None:
        return self._cache_root

    def get_panels(self, request: PanelRequest) -> DailyEodPanels:
        return self.ingest(request).panels

    def ingest(self, request: PanelRequest) -> ThetaIngestResult:
        """Fetch + build panels, and write the cache projection if configured.

        Returns:
            ``ThetaIngestResult`` with both the panel and the per-symbol raw
            paths exposed by the ingestor (useful for ingestion audit tables).
        """
        ingestor = ThetaDataEodIngestor(dataframe_type=self._dataframe_type)
        symbols = list(request.universe.symbols)
        result = ingestor.ingest(
            symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            reuse_cache=self._reuse_cache,
        )
        panels = build_daily_eod_panels(
            result.records,
            list(request.universe.stocks),
            list(request.universe.factor_etfs),
            split_events=request.universe.applicable_splits,
        )
        if self._cache_root is not None:
            self._write_cache_projection(panels)
        return ThetaIngestResult(panels=panels, raw_paths=result.paths)

    def _write_cache_projection(self, panels: DailyEodPanels) -> None:
        assert self._cache_root is not None
        self._cache_root.mkdir(parents=True, exist_ok=True)
        panels.raw_closes.to_csv(self._cache_root / "eod_raw_close_panel.csv")
        if panels.raw_volumes is not None:
            panels.raw_volumes.to_csv(self._cache_root / "eod_raw_volume_panel.csv")
