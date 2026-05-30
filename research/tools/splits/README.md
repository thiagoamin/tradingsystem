# Splits

Pluggable train/test partitioners.

Every splitter returns ``list[Slice]``. Downstream code reads the ``Slice``
fields directly; it does not depend on which splitter produced them.

## Implementation map

- [base.py](base.py)
  - `Slice` -- one fold; carries train/test windows and (optionally) nested
    inner-train/validation windows.
  - `Splitter` -- ABC: `build_slices(start_date, end_date) -> list[Slice]`.
- [walk_forward.py](walk_forward.py)
  - `WalkForwardSplitter` -- rolling or anchored walk-forward, configurable
    train/test window sizes, step, and retrain cadence.
  - `business_days(start, end)` helper (weekday-only inclusive list).
- [nested_walk_forward.py](nested_walk_forward.py)
  - `NestedWalkForwardSplitter` -- wraps a `WalkForwardSplitter`, carves a
    trailing ``validation_window_days`` slice out of each fold's train window
    so candidates can be selected on the inner validation pair, then the
    final model refits on the full train window before scoring on test.
- [single.py](single.py)
  - `SingleSplitter` -- exactly one train/test slice with a configurable cut
    date; defaults to the midpoint of the range.
- [expanding.py](expanding.py)
  - `ExpandingWindowSplitter` -- ``train_start`` fixed at ``start_date``,
    ``train_end`` grows by ``step_days`` per fold, test is the next
    ``test_window_days`` window.

## Slice shape

```python
Slice(
    fold_id=0,
    train_start=date(...),
    train_end=date(...),
    test_start=date(...),
    test_end=date(...),
    should_retrain=True,
    inner_train_start=date(...) | None,
    inner_train_end=date(...) | None,
    validation_start=date(...) | None,
    validation_end=date(...) | None,
)
```

`Slice.has_validation` is the canonical check before reading the nested
fields. Code that only cares about train/test pairs can ignore them.

## How the Sharpe-0.59 strategy splits time

```python
from research.tools.splits import (
    NestedWalkForwardSplitter,
    WalkForwardSplitter,
)

splitter = NestedWalkForwardSplitter(
    validation_window_days=126,
    outer=WalkForwardSplitter(
        train_window_days=504,
        test_window_days=63,
        step_days=63,
        anchored=False,
        retrain_every_n_folds=1,
    ),
)
slices = splitter.build_slices(start_date, end_date)  # 17 nested folds
```

## Relationship to ``research.tools.experiments``

The legacy ``WalkForwardPlan`` / ``TrainTestSlice`` in
``research.tools.experiments.core`` predate this package and have the same
shape as ``WalkForwardSplitter`` / ``Slice``. They remain importable so
existing experiments do not need to be touched. New code should prefer
``research.tools.splits``; the two will be unified in a later pass.

## Where to extend

- ``BlockedKFoldSplitter`` -- non-time-ordered CV with embargo / purging,
  useful for cross-asset signals.
- ``CombinatorialPurgedKFoldSplitter`` -- de Prado-style CPCV when you need
  many folds and overlapping test windows.
- ``CalendarSplitter`` -- split by named regimes (e.g. pre-/post-COVID).

Implement ``Splitter``, return a list of ``Slice``s. No other code changes.
