from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorSpec:
    """Per-stock factor assignments used during residualization."""

    assignments: dict[str, list[str]]

    def __post_init__(self) -> None:
        """Validate that every stock has a non-empty, duplicate-free factor list."""
        if not self.assignments:
            raise ValueError("assignments must be non-empty")
        for stock, factors in self.assignments.items():
            if not isinstance(stock, str) or not stock:
                raise ValueError(f"stock key must be a non-empty string; got {stock!r}")
            if not factors:
                raise ValueError(f"stock '{stock}' has empty factor list")
            if len(set(factors)) != len(factors):
                raise ValueError(f"stock '{stock}' has duplicate factors: {factors}")
            for factor in factors:
                if not isinstance(factor, str) or not factor:
                    raise ValueError(f"factor must be a non-empty string; got {factor!r} for stock '{stock}'")

    @property
    def stocks(self) -> list[str]:
        """Return all stock tickers in insertion order."""
        return list(self.assignments.keys())

    @property
    def all_factors(self) -> list[str]:
        """Return all unique factor tickers in sorted order."""
        factors: set[str] = set()
        for stock_factors in self.assignments.values():
            factors.update(stock_factors)
        return sorted(factors)

    def factors_for(self, stock: str) -> list[str]:
        """Return factor tickers for ``stock`` or raise ``KeyError`` if absent."""
        if stock not in self.assignments:
            raise KeyError(f"stock '{stock}' not in factor spec")
        return list(self.assignments[stock])
