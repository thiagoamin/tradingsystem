from __future__ import annotations

"""Component-level contracts for processors, transformers, predictors, and more."""

from dataclasses import dataclass, field
from typing import Literal

ComponentKind = Literal[
    "data_loader",
    "processor",
    "transformer",
    "predictor",
    "strategy",
    "backtest",
    "evaluator",
    "custom",
]


@dataclass(frozen=True)
class ComponentContract:
    """Declares the inputs and outputs of a reusable pipeline component."""

    name: str
    kind: ComponentKind
    consumes: tuple[str, ...] = field(default_factory=tuple)
    consumes_train: tuple[str, ...] = field(default_factory=tuple)
    consumes_inference: tuple[str, ...] = field(default_factory=tuple)
    produces: tuple[str, ...] = field(default_factory=tuple)
    fit_required: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        if self.kind not in {
            "data_loader",
            "processor",
            "transformer",
            "predictor",
            "strategy",
            "backtest",
            "evaluator",
            "custom",
        }:
            raise ValueError("kind is not a valid ComponentKind")
        for field_name in ("consumes", "consumes_train", "consumes_inference", "produces"):
            object.__setattr__(self, field_name, _normalize_tuple(getattr(self, field_name), field_name))

    @property
    def all_consumes_train(self) -> tuple[str, ...]:
        """Variables needed when fitting or training this component."""
        return _dedupe(self.consumes + self.consumes_train)

    @property
    def all_consumes_inference(self) -> tuple[str, ...]:
        """Variables needed when running this component out-of-sample."""
        return _dedupe(self.consumes + self.consumes_inference)


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _normalize_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates: {normalized}")
    return normalized


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
