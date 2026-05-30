from __future__ import annotations

"""Walk-forward with an inner validation window carved from each train fold."""

from dataclasses import dataclass
from datetime import date

from research.tools.splits.base import Slice, Splitter
from research.tools.splits.walk_forward import WalkForwardSplitter, business_days


@dataclass(frozen=True)
class NestedWalkForwardSplitter(Splitter):
    """Wrap ``WalkForwardSplitter`` and carve a trailing inner-validation slice
    out of each fold's training window.

    For fold with train window ``[train_start, train_end]``, the last
    ``validation_window_days`` business days become the validation slice and
    the rest is the inner-train slice. Candidate selection uses the
    inner-train + validation pair; the final classifier/predictor refits on
    the full train window before evaluating on test.

    Attributes:
        validation_window_days: Length of the inner validation window.
        outer: Underlying ``WalkForwardSplitter`` that produces the
            ``train`` + ``test`` shape.
    """

    validation_window_days: int = 126
    outer: WalkForwardSplitter = WalkForwardSplitter(
        train_window_days=504, test_window_days=63, step_days=63
    )

    def __post_init__(self) -> None:
        if self.validation_window_days < 1:
            raise ValueError("validation_window_days must be >= 1")
        if self.validation_window_days >= self.outer.train_window_days:
            raise ValueError(
                "validation_window_days must be smaller than outer.train_window_days"
            )

    def build_slices(self, start_date: date, end_date: date) -> list[Slice]:
        outer_slices = self.outer.build_slices(start_date, end_date)
        nested: list[Slice] = []
        for outer in outer_slices:
            train_days = business_days(outer.train_start, outer.train_end)
            if len(train_days) <= self.validation_window_days + 20:
                # Tiny window: keep the first 75% as inner train.
                split_idx = max(1, int(len(train_days) * 0.75))
            else:
                split_idx = len(train_days) - self.validation_window_days
            inner_train_end = train_days[split_idx - 1]
            validation_start = train_days[split_idx]
            nested.append(
                Slice(
                    fold_id=outer.fold_id,
                    train_start=outer.train_start,
                    train_end=outer.train_end,
                    test_start=outer.test_start,
                    test_end=outer.test_end,
                    should_retrain=outer.should_retrain,
                    inner_train_start=train_days[0],
                    inner_train_end=inner_train_end,
                    validation_start=validation_start,
                    validation_end=train_days[-1],
                )
            )
        return nested
