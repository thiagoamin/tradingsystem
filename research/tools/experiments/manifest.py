from __future__ import annotations

"""Run manifests for realized experiment outputs."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol


class SliceLike(Protocol):
    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    should_retrain: bool


@dataclass(frozen=True)
class FoldRecord:
    """One realized train/validation/test fold from an experiment run.

    This records what actually happened in a run, including the concrete data
    windows used, whether components were retrained, selected parameters,
    metrics, and artifact paths.
    """

    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    retrained: bool
    inner_train_start: date | None = None
    inner_train_end: date | None = None
    validation_start: date | None = None
    validation_end: date | None = None
    selected_params: Mapping[str, object] = field(default_factory=dict)
    metrics: Mapping[str, object] = field(default_factory=dict)
    artifacts: Mapping[str, str | Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fold_id < 0:
            raise ValueError("fold_id must be non-negative")
        if self.train_start > self.train_end:
            raise ValueError("train_start must be less than or equal to train_end")
        if self.test_start > self.test_end:
            raise ValueError("test_start must be less than or equal to test_end")
        if self.train_end >= self.test_start:
            raise ValueError("train_end must be strictly before test_start")
        _validate_optional_window(self.inner_train_start, self.inner_train_end, "inner_train")
        _validate_optional_window(self.validation_start, self.validation_end, "validation")

    @classmethod
    def from_slice(
        cls,
        slc: SliceLike,
        retrained: bool | None = None,
        selected_params: Mapping[str, object] | None = None,
        metrics: Mapping[str, object] | None = None,
        artifacts: Mapping[str, str | Path] | None = None,
    ) -> FoldRecord:
        """Build a fold record from a splitter ``Slice``."""
        return cls(
            fold_id=slc.fold_id,
            train_start=slc.train_start,
            train_end=slc.train_end,
            test_start=slc.test_start,
            test_end=slc.test_end,
            retrained=slc.should_retrain if retrained is None else retrained,
            inner_train_start=getattr(slc, "inner_train_start", None),
            inner_train_end=getattr(slc, "inner_train_end", None),
            validation_start=getattr(slc, "validation_start", None),
            validation_end=getattr(slc, "validation_end", None),
            selected_params=selected_params or {},
            metrics=metrics or {},
            artifacts=artifacts or {},
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable fold record."""
        return {
            "fold_id": self.fold_id,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "retrained": self.retrained,
            "inner_train_start": _date_or_none(self.inner_train_start),
            "inner_train_end": _date_or_none(self.inner_train_end),
            "validation_start": _date_or_none(self.validation_start),
            "validation_end": _date_or_none(self.validation_end),
            "selected_params": _json_ready(dict(self.selected_params)),
            "metrics": _json_ready(dict(self.metrics)),
            "artifacts": {key: str(value) for key, value in self.artifacts.items()},
        }


@dataclass(frozen=True)
class ExperimentRunManifest:
    """Audit record for one completed experiment run.

    Unlike ``ExperimentContract``, this is not the plan. It is the realized
    record: concrete folds, retrain decisions, selected parameters, metrics,
    and output artifact locations.
    """

    experiment_name: str
    run_id: str
    folds: tuple[FoldRecord, ...]
    contract_name: str | None = None
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    artifacts: Mapping[str, str | Path] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.experiment_name, "experiment_name")
        _require_non_empty(self.run_id, "run_id")
        _require_non_empty(self.created_at_utc, "created_at_utc")
        object.__setattr__(self, "folds", tuple(self.folds))
        if not self.folds:
            raise ValueError("folds must be non-empty")
        fold_ids = [fold.fold_id for fold in self.folds]
        if len(set(fold_ids)) != len(fold_ids):
            raise ValueError(f"fold ids must be unique: {fold_ids}")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable manifest."""
        return {
            "experiment_name": self.experiment_name,
            "run_id": self.run_id,
            "contract_name": self.contract_name,
            "created_at_utc": self.created_at_utc,
            "folds": [fold.to_dict() for fold in self.folds],
            "artifacts": {key: str(value) for key, value in self.artifacts.items()},
            "metadata": _json_ready(dict(self.metadata)),
        }

    def write_json(self, path: str | Path) -> Path:
        """Write the manifest as formatted JSON and return the path."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return output_path


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_ready(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return str(value)
    return value


def _validate_optional_window(start: date | None, end: date | None, name: str) -> None:
    if (start is None) != (end is None):
        raise ValueError(f"{name}_start and {name}_end must both be set or both be None")
    if start is not None and end is not None and start > end:
        raise ValueError(f"{name}_start must be less than or equal to {name}_end")


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
