# Endogenous Horizon

Placeholder for experiments around endogenously chosen trading horizons.

## Status

Theory only. No implementation yet.

## Layout

| Path | Status |
|---|---|
| [theory/core_theory.tex](theory/core_theory/core_theory.tex) | Theory document (work in progress). |
| `<horizon>/` (TBD) | When an implementation lands, it should mirror the per-horizon convention used by `paper_replications/avellaneda_lee_2008/one_day/`. |

The Avellaneda--Lee daily strategy at
`../paper_replications/avellaneda_lee_2008/one_day/` is intended to become
one component of an endogenous-horizon allocation study, per
`replication_plan.tex`. The endogenous-horizon work would sit on top of one
or more such per-horizon sleeves.
