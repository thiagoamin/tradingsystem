from __future__ import annotations

"""Single train/test split with a configurable cut date."""

from dataclasses import dataclass
from datetime import date

from research.tools.splits.base import Slice, Splitter
from research.tools.splits.walk_forward import business_days


@dataclass(frozen=True)
class SingleSplitter(Splitter):
    """Produce exactly one ``Slice`` with train before ``test_start`` and test
    after.

    If ``test_start`` is ``None``, the midpoint of the business-day range is
    used. If ``test_start`` falls outside the range, the midpoint is used.
    """

    test_start: date | None = None

    def build_slices(self, start_date: date, end_date: date) -> list[Slice]:
        days = business_days(start_date, end_date)
        if len(days) < 2:
            raise ValueError("SingleSplitter requires at least two business days.")
        fallback = days[len(days) // 2]
        if self.test_start is None or not (start_date <= self.test_start <= end_date):
            cut = fallback
        else:
            cut = next((day for day in days if day >= self.test_start), fallback)
        train_end_idx = max(0, days.index(cut) - 1)
        return [
            Slice(
                fold_id=0,
                train_start=days[0],
                train_end=days[train_end_idx],
                test_start=cut,
                test_end=days[-1],
                should_retrain=True,
            )
        ]
