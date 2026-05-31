from __future__ import annotations

"""Experiment-level contracts for reproducible strategy evaluation."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from research.tools.contracts.strategy import StrategyContract

ExperimentMode = Literal["single_split", "walk_forward"]


@dataclass(frozen=True)
class ExperimentContract:
    """Declarative contract for one concrete strategy evaluation.

    A strategy contract states what a strategy needs. An experiment contract
    states how that strategy is evaluated: universe, dates, split policy,
    retraining cadence, costs, objectives, and expected artifacts.
    """

    name: str
    strategy: StrategyContract
    start_date: date
    end_date: date
    universe: tuple[str, ...]
    factors: tuple[str, ...] = field(default_factory=tuple)
    mode: ExperimentMode = "walk_forward"
    horizons: tuple[str, ...] = ("1d",)
    train_window_days: int | None = None
    test_window_days: int | None = None
    step_days: int | None = None
    anchored: bool = False
    retrain_every_n_folds: int = 1
    selection_objective: str | None = None
    evaluation_metrics: tuple[str, ...] = field(default_factory=tuple)
    transaction_cost_bps: float | None = None
    output_root: str | Path | None = None
    expected_artifacts: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        if not isinstance(self.strategy, StrategyContract):
            raise TypeError("strategy must be a StrategyContract")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date")
        if self.mode not in {"single_split", "walk_forward"}:
            raise ValueError("mode must be 'single_split' or 'walk_forward'")
        object.__setattr__(self, "universe", _normalize_symbols(self.universe, "universe"))
        object.__setattr__(self, "factors", _normalize_symbols(self.factors, "factors"))
        object.__setattr__(self, "horizons", _normalize_tuple(self.horizons, "horizons"))
        object.__setattr__(self, "evaluation_metrics", _normalize_tuple(self.evaluation_metrics, "evaluation_metrics"))
        object.__setattr__(self, "expected_artifacts", _normalize_tuple(self.expected_artifacts, "expected_artifacts"))
        if not self.universe:
            raise ValueError("universe must be non-empty")
        if self.mode == "walk_forward":
            self._validate_walk_forward()
        if self.transaction_cost_bps is not None and self.transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")
        if self.selection_objective is not None and not self.selection_objective.strip():
            raise ValueError("selection_objective cannot be blank")

    @property
    def all_symbols(self) -> tuple[str, ...]:
        """Universe and factor symbols, deduplicated in dependency order."""
        return tuple(dict.fromkeys(self.universe + self.factors))

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable metadata for audit artifacts."""
        return {
            "name": self.name,
            "description": self.description,
            "strategy": self.strategy.name,
            "strategy_frequency": self.strategy.frequency,
            "mode": self.mode,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "universe": list(self.universe),
            "factors": list(self.factors),
            "horizons": list(self.horizons),
            "train_window_days": self.train_window_days,
            "test_window_days": self.test_window_days,
            "step_days": self.step_days,
            "anchored": self.anchored,
            "retrain_every_n_folds": self.retrain_every_n_folds,
            "selection_objective": self.selection_objective,
            "evaluation_metrics": list(self.evaluation_metrics),
            "transaction_cost_bps": self.transaction_cost_bps,
            "output_root": str(self.output_root) if self.output_root is not None else None,
            "expected_artifacts": list(self.expected_artifacts),
        }

    def _validate_walk_forward(self) -> None:
        if self.train_window_days is None or self.train_window_days < 2:
            raise ValueError("walk_forward experiments require train_window_days >= 2")
        if self.test_window_days is None or self.test_window_days < 1:
            raise ValueError("walk_forward experiments require test_window_days >= 1")
        if self.step_days is None or self.step_days < 1:
            raise ValueError("walk_forward experiments require step_days >= 1")
        if self.retrain_every_n_folds < 1:
            raise ValueError("retrain_every_n_folds must be >= 1")


def _normalize_symbols(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    return _normalize_tuple(tuple(value.upper() for value in values), name)


def _normalize_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates: {normalized}")
    return normalized


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
