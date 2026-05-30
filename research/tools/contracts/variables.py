from __future__ import annotations

"""Derived variable specifications for strategy pipelines."""

from dataclasses import dataclass, field
from typing import Literal

VariableTiming = Literal["event_time", "bar_close", "t_minus_1", "same_time", "unknown"]
VariableRole = Literal["feature", "target", "signal_input", "risk_input", "execution_input", "output"]


@dataclass(frozen=True)
class VariableSpec:
    """A named derived variable consumed or produced by pipeline components.

    Examples include ``daily_returns``, ``factor_betas``, ``spread_bps``,
    ``signed_volume_imbalance``, ``regime_probabilities``, and ``target_weights``.
    """

    name: str
    role: VariableRole
    dtype: str = "float"
    frequency: str | None = None
    scope: str | None = None
    timing: VariableTiming = "unknown"
    required_inputs: tuple[str, ...] = field(default_factory=tuple)
    producer: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        if self.role not in {"feature", "target", "signal_input", "risk_input", "execution_input", "output"}:
            raise ValueError("role is not a valid VariableRole")
        if self.timing not in {"event_time", "bar_close", "t_minus_1", "same_time", "unknown"}:
            raise ValueError("timing is not a valid VariableTiming")
        object.__setattr__(self, "required_inputs", _normalize_tuple(self.required_inputs, "required_inputs"))


def _normalize_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates: {normalized}")
    return normalized


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
