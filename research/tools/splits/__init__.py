"""Pluggable train/test splitters.

Every splitter returns a list of ``Slice`` records with the same shape. The
``inner_train`` / ``validation`` fields are populated only by nested-CV style
splitters; flat splitters leave them ``None``. Downstream code should branch on
``slice.has_validation`` rather than on splitter type.
"""

from research.tools.splits.base import Slice, Splitter
from research.tools.splits.expanding import ExpandingWindowSplitter
from research.tools.splits.nested_walk_forward import NestedWalkForwardSplitter
from research.tools.splits.single import SingleSplitter
from research.tools.splits.walk_forward import WalkForwardSplitter, business_days

__all__ = [
    "ExpandingWindowSplitter",
    "NestedWalkForwardSplitter",
    "SingleSplitter",
    "Slice",
    "Splitter",
    "WalkForwardSplitter",
    "business_days",
]
