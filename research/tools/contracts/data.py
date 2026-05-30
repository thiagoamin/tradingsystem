from __future__ import annotations

"""Generic data-source requirements for research pipelines."""

from dataclasses import dataclass, field
from typing import Literal

RequirementUse = Literal["train", "inference", "train_and_inference"]


@dataclass(frozen=True)
class DataRequirement:
    """Raw or external data needed by a strategy pipeline.

    The requirement is intentionally not limited to market data. Use ``domain``
    to distinguish sources such as ``"market"``, ``"fundamental"``,
    ``"macro"``, ``"news"``, ``"portfolio"``, or ``"broker_state"``.
    """

    name: str
    domain: str
    kind: str
    fields: tuple[str, ...] = field(default_factory=tuple)
    source: str | None = None
    frequency: str | None = None
    scope: str | None = None
    required_for: RequirementUse = "train_and_inference"
    description: str = ""

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        _require_non_empty(self.domain, "domain")
        _require_non_empty(self.kind, "kind")
        if self.required_for not in {"train", "inference", "train_and_inference"}:
            raise ValueError("required_for must be 'train', 'inference', or 'train_and_inference'")
        object.__setattr__(self, "fields", _normalize_tuple(self.fields, "fields"))


def _normalize_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates: {normalized}")
    return normalized


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
