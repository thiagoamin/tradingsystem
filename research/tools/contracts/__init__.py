"""Declarative contracts for data, variables, components, and strategies."""

from research.tools.contracts.components import ComponentContract, ComponentKind
from research.tools.contracts.data import DataRequirement, RequirementUse
from research.tools.contracts.runtime import StrategyRunContext
from research.tools.contracts.strategy import StrategyContract
from research.tools.contracts.variables import VariableRole, VariableSpec, VariableTiming

__all__ = [
    "ComponentContract",
    "ComponentKind",
    "DataRequirement",
    "RequirementUse",
    "StrategyContract",
    "StrategyRunContext",
    "VariableRole",
    "VariableSpec",
    "VariableTiming",
]
