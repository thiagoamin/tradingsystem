from __future__ import annotations

"""Rolling or anchored walk-forward train/test partitioning."""

from dataclasses import dataclass
from datetime import date, timedelta

from research.tools.splits.base import Slice, Splitter


def business_days(start_date: date, end_date: date) -> list[date]:
    """Inclusive list of weekday dates between ``start_date`` and ``end_date``."""
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


@dataclass(frozen=True)
class WalkForwardSplitter(Splitter):
    """Tile the time window into consecutive train/test slices.

    With ``anchored=False`` (default) the train window slides with the test
    window. With ``anchored=True`` the train window grows; the start date
    is fixed and only ``train_end`` advances.

    Attributes:
        train_window_days: Length of each train window in business days.
        test_window_days: Length of each test window in business days.
        step_days: Distance between successive ``test_start`` values.
        anchored: If ``True``, all folds share ``train_start = start_date``.
        retrain_every_n_folds: ``should_retrain`` is ``True`` on every Nth fold
            (counting from 0).
    """

    train_window_days: int = 60
    test_window_days: int = 20
    step_days: int = 20
    anchored: bool = False
    retrain_every_n_folds: int = 1

    def __post_init__(self) -> None:
        if self.train_window_days < 2:
            raise ValueError("train_window_days must be >= 2")
        if self.test_window_days < 1:
            raise ValueError("test_window_days must be >= 1")
        if self.step_days < 1:
            raise ValueError("step_days must be >= 1")
        if self.retrain_every_n_folds < 1:
            raise ValueError("retrain_every_n_folds must be >= 1")

    def build_slices(self, start_date: date, end_date: date) -> list[Slice]:
        days = business_days(start_date, end_date)
        if len(days) < self.train_window_days + self.test_window_days:
            raise ValueError("Date range is too short for configured walk-forward windows.")
        slices: list[Slice] = []
        fold_id = 0
        test_start_idx = self.train_window_days
        while test_start_idx < len(days):
            train_start_idx = 0 if self.anchored else max(0, test_start_idx - self.train_window_days)
            train_end_idx = test_start_idx - 1
            test_end_idx = min(test_start_idx + self.test_window_days - 1, len(days) - 1)
            if train_end_idx <= train_start_idx:
                break
            slices.append(
                Slice(
                    fold_id=fold_id,
                    train_start=days[train_start_idx],
                    train_end=days[train_end_idx],
                    test_start=days[test_start_idx],
                    test_end=days[test_end_idx],
                    should_retrain=(fold_id % self.retrain_every_n_folds == 0),
                )
            )
            fold_id += 1
            test_start_idx += self.step_days
        if not slices:
            raise ValueError("No walk-forward slices were generated with the current configuration.")
        return slices
