from __future__ import annotations

"""Strategy-level pipeline contracts."""

from dataclasses import dataclass, field

from research.tools.contracts.components import ComponentContract
from research.tools.contracts.data import DataRequirement
from research.tools.contracts.variables import VariableSpec


@dataclass(frozen=True)
class StrategyContract:
    """Complete dependency contract for training and running a strategy.

    The contract is declarative: it does not execute the pipeline. It states
    which data, variables, and components must exist before a strategy can be
    trained or used for inference.
    """

    name: str
    description: str = ""
    frequency: str | None = None
    data_requirements: tuple[DataRequirement, ...] = field(default_factory=tuple)
    variables: tuple[VariableSpec, ...] = field(default_factory=tuple)
    components: tuple[ComponentContract, ...] = field(default_factory=tuple)
    train_variables: tuple[str, ...] = field(default_factory=tuple)
    inference_variables: tuple[str, ...] = field(default_factory=tuple)
    output_variables: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        for field_name in ("train_variables", "inference_variables", "output_variables"):
            object.__setattr__(self, field_name, _normalize_tuple(getattr(self, field_name), field_name))
        self._validate_unique_names()
        self._validate_references()

    @property
    def variable_names(self) -> tuple[str, ...]:
        """All declared variable names."""
        return tuple(variable.name for variable in self.variables)

    @property
    def component_names(self) -> tuple[str, ...]:
        """All declared component names."""
        return tuple(component.name for component in self.components)

    @property
    def train_data_requirements(self) -> tuple[DataRequirement, ...]:
        """Data required for training."""
        return tuple(req for req in self.data_requirements if req.required_for in {"train", "train_and_inference"})

    @property
    def inference_data_requirements(self) -> tuple[DataRequirement, ...]:
        """Data required for inference."""
        return tuple(req for req in self.data_requirements if req.required_for in {"inference", "train_and_inference"})

    def required_variables(self, mode: str) -> tuple[str, ...]:
        """Return required variable names for ``train`` or ``inference`` mode."""
        if mode == "train":
            return self.train_variables
        if mode == "inference":
            return self.inference_variables
        raise ValueError("mode must be 'train' or 'inference'")

    def _validate_unique_names(self) -> None:
        _ensure_unique((req.name for req in self.data_requirements), "data requirement")
        _ensure_unique((var.name for var in self.variables), "variable")
        _ensure_unique((component.name for component in self.components), "component")

    def _validate_references(self) -> None:
        names = set(self.variable_names)
        referenced = set(self.train_variables) | set(self.inference_variables) | set(self.output_variables)
        for component in self.components:
            referenced.update(component.consumes)
            referenced.update(component.consumes_train)
            referenced.update(component.consumes_inference)
            referenced.update(component.produces)
        missing = sorted(referenced - names)
        if missing:
            raise ValueError(f"contract references undeclared variables: {missing}")


def _ensure_unique(values, label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"duplicate {label} names are not allowed: {items}")


def _normalize_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(str(value).strip() for value in values if str(value).strip())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates: {normalized}")
    return normalized


def _require_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
