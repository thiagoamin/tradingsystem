from __future__ import annotations

"""``Splitter`` ABC + ``Slice`` record."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Slice:
    """One train/test (and optional validation) window.

    The ``inner_train_*`` and ``validation_*`` dates are populated only by
    nested-CV style splitters (e.g. ``NestedWalkForwardSplitter``). Flat
    splitters set them to ``None``.

    Attributes:
        fold_id: Position in the sequence returned by ``Splitter.build_slices``.
        train_start: First training-window day.
        train_end: Last training-window day.
        test_start: First test-window day.
        test_end: Last test-window day.
        should_retrain: Hint for the runner about whether to refit
            transformers/predictors on this fold (always ``True`` for the
            non-cacheing default).
        inner_train_start: First inner-train day (nested only).
        inner_train_end: Last inner-train day (nested only).
        validation_start: First validation day (nested only).
        validation_end: Last validation day (nested only).
    """

    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    should_retrain: bool = True
    inner_train_start: date | None = None
    inner_train_end: date | None = None
    validation_start: date | None = None
    validation_end: date | None = None

    @property
    def has_validation(self) -> bool:
        return self.validation_start is not None and self.validation_end is not None


class Splitter(ABC):
    """Produce an ordered list of ``Slice`` records for ``[start_date, end_date]``."""

    @abstractmethod
    def build_slices(self, start_date: date, end_date: date) -> list[Slice]:
        """Returns slices in chronological order.

        Raises:
            ValueError: If the window cannot accommodate the requested
                configuration.
        """
