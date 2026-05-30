from __future__ import annotations

"""Runtime context and validation for strategy contracts."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from research.tools.contracts.strategy import StrategyContract


@dataclass(frozen=True)
class StrategyRunContext:
    """Concrete objects available when training or running a strategy.

    ``data`` holds raw/external data keyed by data requirement name.
    ``variables`` holds derived panels or objects keyed by variable name.
    ``fitted_components`` holds trained transformers or predictors.
    """

    data: Mapping[str, Any] = field(default_factory=dict)
    variables: Mapping[str, Any] = field(default_factory=dict)
    fitted_components: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, contract: StrategyContract, mode: str) -> None:
        """Validate that this context satisfies a strategy contract.

        Args:
            contract: Strategy contract to validate against.
            mode: Either ``"train"`` or ``"inference"``.

        Raises:
            ValueError: If required data or variables are absent.
        """
        if mode not in {"train", "inference"}:
            raise ValueError("mode must be 'train' or 'inference'")
        data_requirements = (
            contract.train_data_requirements if mode == "train" else contract.inference_data_requirements
        )
        missing_data = sorted(req.name for req in data_requirements if req.name not in self.data)
        missing_variables = sorted(name for name in contract.required_variables(mode) if name not in self.variables)
        if missing_data or missing_variables:
            parts: list[str] = []
            if missing_data:
                parts.append(f"missing data: {missing_data}")
            if missing_variables:
                parts.append(f"missing variables: {missing_variables}")
            raise ValueError("StrategyRunContext does not satisfy contract: " + "; ".join(parts))

    def require_data(self, name: str) -> Any:
        """Return a required data object or raise ``KeyError``."""
        if name not in self.data:
            raise KeyError(f"data object '{name}' is not available")
        return self.data[name]

    def require_variable(self, name: str) -> Any:
        """Return a required variable object or raise ``KeyError``."""
        if name not in self.variables:
            raise KeyError(f"variable '{name}' is not available")
        return self.variables[name]

    def require_component(self, name: str) -> Any:
        """Return a required fitted component or raise ``KeyError``."""
        if name not in self.fitted_components:
            raise KeyError(f"fitted component '{name}' is not available")
        return self.fitted_components[name]
