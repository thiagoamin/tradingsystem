from __future__ import annotations

"""Expanding-window walk-forward: train grows, test steps forward."""

from dataclasses import dataclass
from datetime import date

from research.tools.splits.base import Slice, Splitter
from research.tools.splits.walk_forward import business_days


@dataclass(frozen=True)
class ExpandingWindowSplitter(Splitter):
    """Train always starts at ``start_date`` and grows by ``step_days`` each
    fold; test is the next ``test_window_days`` window.

    Attributes:
        initial_train_days: Length of the first training window.
        test_window_days: Length of each test window.
        step_days: Distance between successive ``test_start`` values.
        retrain_every_n_folds: ``should_retrain`` is ``True`` on every Nth fold.
    """

    initial_train_days: int = 504
    test_window_days: int = 63
    step_days: int = 63
    retrain_every_n_folds: int = 1

    def __post_init__(self) -> None:
        if self.initial_train_days < 2:
            raise ValueError("initial_train_days must be >= 2")
        if self.test_window_days < 1:
            raise ValueError("test_window_days must be >= 1")
        if self.step_days < 1:
            raise ValueError("step_days must be >= 1")
        if self.retrain_every_n_folds < 1:
            raise ValueError("retrain_every_n_folds must be >= 1")

    def build_slices(self, start_date: date, end_date: date) -> list[Slice]:
        days = business_days(start_date, end_date)
        if len(days) < self.initial_train_days + self.test_window_days:
            raise ValueError("Date range is too short for expanding-window configuration.")
        slices: list[Slice] = []
        fold_id = 0
        test_start_idx = self.initial_train_days
        while test_start_idx < len(days):
            train_end_idx = test_start_idx - 1
            test_end_idx = min(test_start_idx + self.test_window_days - 1, len(days) - 1)
            slices.append(
                Slice(
                    fold_id=fold_id,
                    train_start=days[0],
                    train_end=days[train_end_idx],
                    test_start=days[test_start_idx],
                    test_end=days[test_end_idx],
                    should_retrain=(fold_id % self.retrain_every_n_folds == 0),
                )
            )
            fold_id += 1
            test_start_idx += self.step_days
        if not slices:
            raise ValueError("No expanding-window slices were generated.")
        return slices
