# Avellaneda--Lee (2008) Daily Residual Replication and Extensions

This directory implements the daily ETF-residual statistical-arbitrage strategy
described in Avellaneda \& Lee, *Statistical Arbitrage in the U.S. Equities
Market* (2008), restricted to modern U.S. equities (Jan 2020--Dec 2025), and
the two extensions documented under
`research/theory/paper_replications/avellaned&lee_2008/`:

- `replication_plan.tex` -- the assigned-sector-ETF baseline.
- `residual_trend_extension.tex` -- a regime-switching extension where each
  stock-date can be traded as residual mean-reversion **or** residual
  trend-following, with a logistic classifier picking the mode.

The implementation is split between **reusable tools** in `research/tools/`
(transformer, predictor, strategy, backtest, evaluation) and **experiment
scripts** in this folder. Each script is a thin orchestration around the
tool layer; tuning and universe choices live in the scripts, the maths lives
in the tools.

## Contents

| Script | Purpose | Status |
|---|---|---|
| [ingest_theta_eod_data.py](ingest_theta_eod_data.py) | Pull EOD closes + volume from ThetaData for the 12-tech-stock universe + {SPY, XLK, QQQ}, apply audited splits | Required first run; cached afterwards |
| [configured_splits.py](configured_splits.py) | Hand-audited stock-split schedule for raw ThetaData closes (AAPL 2020, NVDA 2021/2024, AVGO 2024, XLK 2025, XLE 2025) | Maintained by hand; ingestion errors out on unconfigured discontinuities |
| [rolling_etf_residualization.py](rolling_etf_residualization.py) | Builds rolling-OLS residual panels from the tech universe vs. {SPY, XLK, QQQ} for inspection | Diagnostic |
| [estimate_ou_scores.py](estimate_ou_scores.py) | Reports per-stock OU eligibility, kappa, and s-score distributions on the tech panel | Diagnostic |
| [backtest_s_score_strategy.py](backtest_s_score_strategy.py) | **Paper baseline.** Single-factor OU s-score with stateful entry/exit at +/-1.25 / 0.75 / -0.50 | Stable, paper-faithful |
| [sector_etf/](sector_etf/) | 25-stock five-sector universe (5 tech, 5 fin, 5 energy, 5 health, 5 industrial) + matching ingestion + paper-style assigned-ETF s-score backtest | Stable |
| [compare_hedge_fractions.py](compare_hedge_fractions.py) | Sweeps `hedge_fraction` $\gamma \in \{0,0.25,...,1\}$ on the paper baseline | Diagnostic |
| [hybrid_residual_diagnostics.py](hybrid_residual_diagnostics.py) | Full-data hybrid (regime-switching) walk-forward, no inner tuning. Defines `DiagnosticConfig` reused below | Stable |
| [hybrid_residual_nested_tuning.py](hybrid_residual_nested_tuning.py) | **Live best (tech).** Nested walk-forward: inner 126-day validation selects from a candidate grid (mean-reversion / inverse-trend / hybrid families), outer test once. Vol-target sizing enabled | **Sharpe 0.59 OOS** |
| [multi_sector_hybrid_nested_tuning.py](multi_sector_hybrid_nested_tuning.py) | Same nested tuning as `hybrid_residual_nested_tuning.py` but on the 25-stock five-sector universe. Currently configured for dual-factor (SPY + sector ETF) residualization on `{XLF, XLE}`, single-factor elsewhere | Sharpe -0.26 OOS (does not beat tech-only) |

## Universes And Factor Specifications

Three universes are in current use, all daily-frequency, 2020-01-02 to
2025-12-31. Trading evaluation begins after the 504-day warmup that
nested-tuning requires for the inner validation window.

### Tech 12

Defined in [ingest_theta_eod_data.py](ingest_theta_eod_data.py):

| Bucket | Symbols |
|---|---|
| Stocks (12) | AAPL, MSFT, NVDA, AVGO, AMD, ADBE, CRM, CSCO, INTC, ORCL, QCOM, TXN |
| Factor ETFs (3) | XLK (primary), SPY, QQQ |

All 12 stocks are residualized against a single factor (XLK by default). This
is the universe driving the **Sharpe 0.59** live-best result.

### Sector-ETF Five-Sector 25

Defined in [sector_etf/config.py](sector_etf/config.py):

| Sector ETF | Stocks |
|---|---|
| XLK | AAPL, MSFT, NVDA, AVGO, AMD |
| XLF | JPM, BAC, GS, MS, C |
| XLE | XOM, CVX, COP, SLB, EOG |
| XLV | LLY, JNJ, MRK, ABBV, UNH |
| XLI | CAT, HON, UNP, UPS, LMT |
| Market factor | SPY (added for multi-factor residualization in the multi-sector experiment) |

Each stock is assigned to its sector ETF as the primary factor. The
`multi_sector_hybrid_nested_tuning.py` script optionally adds SPY as a second
factor for sectors listed in `DUAL_FACTOR_SECTORS` (currently `{XLF, XLE}`).

### Robustness Triple (12 stocks)

Same 12 tech names but residualized against `[SPY, XLK, QQQ]`. Tested in
`backtest_s_score_strategy.py` -- worse than primary XLK only.

## Pipeline

The same five-stage pipeline backs every script in this folder.

```
raw EOD records (ThetaData)
        |
        |  build_daily_eod_panels + configured_splits.RAW_CLOSE_SPLIT_EVENTS
        v
DailyEodPanels(closes, returns, volumes, dollar_volumes, ...)
        |
        |  RollingFactorResidualizationModel
        |    -- FactorSpec defines stock -> [factors]
        |    -- RollingOLSExposureEstimator(window=60, fit_intercept=True)
        v
residual returns (per-stock, lookahead-safe) + rolling beta paths
        |
        |  ResidualStateTransformer (level_window=60, trend_window=20,
        |  volatility_window=20, volume_window=60, ou_estimator=None|OUEstimator)
        v
ResidualStateResult: displacement_score, trend_score, trend_slope, trend_r2,
                    residual_level, residual_volatility, relative_volume,
                    dollar_volume_zscore, (ou_s_score, ou_mean_reversion_days)
        |
        |  ResidualRegimePredictor (one logistic classifier per stock)
        |    fit on training-fold inner-train slice of the state features
        |    target = build_residual_regime_target(...) -- 1 if trend-follow was
        |    the better next-day move, 0 if mean-revert was, else NaN
        v
P(trend regime) panel
        |
        |  HybridResidualStrategy
        |    entry/exit thresholds on probability AND on |s^MR|, |s^TR|
        |    mode -> {mean_reversion, trend, flat}
        |    direction -> sign(trend_score) or -sign(displacement_score)
        v
signals in {-1, 0, +1} + per-stock mode labels
        |
        |  FactorHedgedDailyBacktestEngine
        |    per-stock weights = stock_weight * vol_multiplier * signal
        |    hedge each ETF f by -hedge_fraction * sum_i (weight_i * beta_{i,f})
        |    optional portfolio-vol scaling
        |    cap to gross_exposure_limit
        |    transaction_cost = 5 bps per dollar of |w_t - w_{t-1}|
        v
FactorHedgedBacktestResult: target_weights, asset_pnl, portfolio_pnl,
                            exposure_diagnostics (gross, net, factor exposures,
                            portfolio_vol_scale, turnover)
        |
        |  BasicStrategyEvaluator + HybridModeAttributionEvaluator
        v
summary metrics + mode attribution (gross/net/cost by mean_reversion / trend /
inverse_trend / flat) + stock-level activity
```

### No-Lookahead Discipline

- Beta path: rolling OLS uses observations strictly before $t$ (see
  `RollingOLSExposureEstimator`). The residual at $t$ uses $\widehat\beta_{i,t}$
  estimated from $[t-M, t-1]$.
- Residual state: `ResidualStateTransformer` internally calls
  `residual_returns.shift(1)` before computing every rolling feature, so each
  state value at $t$ uses residuals through $t-1$ only.
- Regime classifier: fit per fold on training-fold features, predicted on
  test-fold features. The nested-tuning variant adds an inner 126-day
  validation split: the inner classifier scores candidate thresholds, the
  final (refit) classifier predicts the outer test window once.
- Strategy: stateful but only consumes inputs dated $\le t$. Position at $t$
  is paired with return $R_t$ in the engine (which already accounts for the
  upstream shift).
- Vol targeting: trailing portfolio vol uses `pre_pnl.shift(1).rolling(...)`,
  so the scale at $t$ is computed from PnL through $t-1$.

The engine's input validator (`FactorHedgedDailyBacktestEngine._validate_inputs`)
checks symbol/index alignment and refuses to apply a nonzero target weight to
a stock whose realized return or beta is missing.

## Walk-Forward Protocol

Default for `hybrid_residual_diagnostics.py` and the nested-tuning variants:

| Param | Value | Meaning |
|---|---|---|
| `train_window_days` | 504 | ~2 years of trading days per outer training window |
| `test_window_days` | 63 | ~3 months held-out test |
| `step_days` | 63 | folds tile the test window without overlap |
| `anchored` | `False` | rolling, not expanding |
| `retrain_every_n_folds` | 1 | refit the classifier each fold |

Nested variant additionally sets:

| Param | Value | Meaning |
|---|---|---|
| `validation_window_days` | 126 | inner validation slice carved from the **end** of the training window |
| `objective` | `"sharpe"` | candidate ranking metric on the validation slice |
| `min_validation_active_rate` | 0.03 | candidates trading < 3% of validation days are disqualified |

## Strategy Candidates (Hybrid Nested Tuning)

`_candidate_grid()` builds three families, all evaluated through the same
`HybridResidualStrategy` plumbing:

1. **Mean-reversion only.** `mr_probability_entry in {0.30, 0.35, 0.40}` and
   `mr_entry_score in {1.25, 1.50, 1.75, 2.00}` -- 12 candidates. Trend mode
   thresholds set unreachably high. Direction is `-sign(displacement_score)`.
2. **Inverse-trend only.** `trend_probability_entry in {0.60, 0.65, 0.70}` and
   `trend_entry_score in {1.00, 1.25, 1.50}`, with the strategy run in trend
   mode then sign-flipped via `_invert_trend_signals`. Direction is
   `-sign(trend_score)`. Requires `min_trend_r2=0.10` and
   `min_relative_volume_for_trend=0.8`. 9 candidates.
3. **Mean-reversion plus inverse-trend.** MR has priority; only if no MR
   entry fires does the inverse-trend rule get a shot. `mr_probability in
   {0.30, 0.35}`, `mr_score in {1.50, 1.75}`, `trend_probability in
   {0.65, 0.70}`, `trend_score in {1.25, 1.50}` -- 16 candidates.

Total: 37 candidates per outer fold. Inner-validation Sharpe picks one
candidate; the outer test fold evaluates that candidate once.

The "inverse-trend" name is literal: this family runs the trend-mode entry
rule and then flips the sign. It is operationally identical to mean-reversion
triggered by the **trend** score rather than by the displacement score, and
its empirical success in tech (see `summary.txt` mode attribution) was the
strongest single insight from this experiment line. **It does not generalize
to other sectors** (see Multi-Sector Findings below).

## Backtest Configuration

Defaults in `DiagnosticConfig`:

| Param | Value |
|---|---|
| `start_date`, `end_date` | 2020-01-02, 2025-12-31 |
| `factor` | XLK (single-factor in tech experiments; per-stock in multi-sector) |
| `residual_window_days` | 60 |
| `state_level_window` | 60 |
| `state_trend_window` | 20 |
| `state_volatility_window` | 20 |
| `state_volume_window` | 60 |
| `min_regime_obs` | 150 (minimum labels per stock for the classifier) |
| `min_target_score` | 0.25 (minimum |trend|, |displacement| to label a regime) |
| `stock_weight` | 0.05 |
| `gross_exposure_limit` | 2.0 |
| `transaction_cost_bps` | 5.0 |
| `hedge_fraction` | 1.0 |

Vol-targeting fields (added during the improvement work):

| Param | Default | Live setting in nested tuning |
|---|---|---|
| `residual_volatility_target` | `None` | **0.015** (daily, i.e. ~24% annualized residual vol target per active stock) |
| `max_position_multiplier` | 3.0 | 3.0 |
| `portfolio_vol_target` | `None` | `None` (kept off; see results below) |
| `portfolio_vol_lookback` | 20 | 20 |
| `max_portfolio_scale` | 15.0 | 15.0 |
| `enable_ou_score` | `False` | `False` |
| `ou_max_mean_reversion_days` | 30.0 | 30.0 |

The vol-targeting maths is documented in
`research/tools/backtest/README.md`. The OU s-score / `mr_score_source` option
is documented in `research/tools/transformer/residual_state/README.md` and
`research/tools/strategy/README.md`.

## How To Run

Each script supports `python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.<name>`.

ThetaData ingestion needs `creds.txt` resolvable from cwd. The repo
convention is to symlink it from `research/fetchers/thetadata/creds.txt`:

```bash
cd /Users/thiagoamin/Desktop/trading_system
ln -sf research/fetchers/thetadata/creds.txt creds.txt
```

Typical sequence (tech only):

```bash
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.ingest_theta_eod_data
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.backtest_s_score_strategy
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_diagnostics
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.hybrid_residual_nested_tuning
```

For the 25-stock universe:

```bash
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.sector_etf.ingest_theta_eod_data
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.sector_etf.backtest_s_score_strategy
python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.multi_sector_hybrid_nested_tuning
```

All scripts write to
`research/experiment_outputs/avellaneda_lee_2008/one_day/<script_name>/` -- one
folder per experiment, containing `config.csv`, `summary.csv`, `summary.txt`,
per-fold artifacts, and stitched OOS panels.

## Results Tour

OOS metrics are stitched across walk-forward test folds. Annualization factor
is 252. Costs are 5 bps per dollar of position change throughout.

### Paper Baselines (No Hybrid)

| Spec | Universe | Sharpe | Cum Return | Active Rate | Source |
|---|---|---|---|---|---|
| Primary XLK single-factor s-score | Tech 12 | -0.53 | -7.0% | 96% | `backtest_s_score_strategy.py` |
| SPY+XLK+QQQ robustness | Tech 12 | -0.62 | -8.3% | 96% | `backtest_s_score_strategy.py` |
| Assigned sector-ETF s-score | Sector-ETF 25 | (paper-style baseline -- see `sector_etf/backtest_s_score_strategy.py`) | | | |

The pure paper-style fade does not work in this universe in 2020--2025. The
strategy is active nearly every day, generates negative gross PnL, then pays
costs on top. This is the motivating finding that the regime-switching
extension is trying to address.

### Hybrid (Regime-Switching) Tuning Track

| Variant | Sharpe | Cum Return | Notes |
|---|---|---|---|
| `hybrid_residual_diagnostics` (no inner tuning) | (see `summary.txt` in its output dir) | | classifier predicts trend/MR, strategy uses default thresholds |
| `hybrid_residual_nested_tuning`, no vol target | 0.41 | 1.3% | this was the starting point of the improvement track |
| `hybrid_residual_nested_tuning`, **per-stock residual-vol target = 0.015** | **0.59** | 2.57% | live best |
| same, plus portfolio-vol target 0.005 / lookback 20 | -0.15 | -6.47% | regressed; see Postmortem |
| same, plus portfolio-vol target 0.003 / lookback 60 | 0.52 | 3.93% | gentler overlay still regresses |

The Sharpe-0.59 row is the current live best. Mode attribution under that
configuration:

| Mode | Sharpe | Active rate | Note |
|---|---|---|---|
| mean_reversion | 0.51 | 27% | up from 0.16 without per-stock vol target |
| inverse_trend | 0.36 | 11% | slightly down from 0.42 (high-vol names get downweighted) |
| flat | -- | -- | -- |

### OU S-Score Experiment

Added the Avellaneda--Lee OU s-score $(X_{i,t-1}-\widehat m_i)/\widehat\sigma_{eq,i}$
to the state transformer and made it switchable in `HybridResidualStrategy`
via `mr_score_source`. Tested three uses:

| Variant | Sharpe |
|---|---|
| OU as MR trigger AND in target builder, original thresholds | -0.47 |
| OU as MR trigger AND in target builder, thresholds rescaled to 0.75--1.5 (OU s-scores are ~60% the magnitude of displacement scores) | -0.38 |
| OU as extra classifier feature only, displacement still triggers | 0.12 |

All three regressed vs. the displacement-score baseline. The OU parameters
(equilibrium mean $m$ and equilibrium std $\sigma_{eq}$) are fragile when the
underlying residual isn't actually OU -- common in trending tech residuals.
The path-z-score is more robust precisely because it imposes no stationary
equilibrium. The OU machinery is left in place behind the
`enable_ou_score` config flag for use in universes where the OU assumption is
more credible.

### Multi-Sector Findings

Expanding from 12 tech stocks to the 25-stock five-sector universe with each
stock residualized against its assigned sector ETF:

| Variant | Sharpe | Cum Return |
|---|---|---|
| Full candidate grid (MR + inverse-trend + hybrid), single-factor | -0.66 | -2.5% |
| MR-only grid, single-factor | -0.06 | -0.3% |
| 3 sectors (XLK + XLV + XLI), MR-only, single-factor | 0.12 | 0.5% |
| Full grid, dual-factor [SPY, sector] for all stocks | -0.44 | -1.9% |
| Full grid, dual-factor for `{XLF, XLE}` only | **-0.26** | -1.0% |
| Full grid, dual-factor for `{XLF}` only | -0.47 | -1.9% |

Per-sector net PnL under MR-only single-factor:

| Sector | Net PnL (3-year OOS) |
|---|---|
| XLK | +1.38% |
| XLV | +0.08% |
| XLI | -0.18% |
| XLF | -0.74% |
| XLE | -0.89% |

XLF and XLE wipe out the gains from XLK/XLV. Dual-factor residualization
(SPY + sector) is the right mechanism for XLF: per-sector stocks-plus-hedge
PnL flipped from -0.74% to +0.74% (a ~1.5% improvement). But the additional
short-SPY hedge brought a -1.05% market-trend drag because SPY rallied
through most of the OOS window. The two effects roughly cancel.

**Net read on the multi-sector track:** the strategy as currently formulated
captures a tech-specific edge (driven heavily by the inverse-trend rule in
XLK + clean residual MR in XLK/XLV). Naive expansion to other sectors
underperforms tech-only, even after a principled residualization fix. The
honest next steps -- not yet implemented -- are:

- **Per-sector threshold tuning** (let each sector pick its own
  family/threshold from the grid).
- **Cross-sectional residualization** (subtract sector-mean rather than
  regress on sector ETF) to avoid SPY-hedge drag.
- **Sector regime gating** (only trade a sector when its sector ETF is in a
  low-vol or low-trend regime).
- **More refined factor portfolios** (KBE/KRE for banks instead of SPY+XLF;
  USO for energy) -- requires new ThetaData ingestion.

## Postmortem: What Did Not Work And Why

This is intentionally explicit to avoid relitigating.

**Portfolio-level vol targeting (audit item #4).** On a 12-stock tech panel
with already-narrow active counts, the per-stock vol target already pushes
positions near the gross cap on active days. Layering a portfolio-vol
overlay on top fires aggressively during quiet stretches (scale climbs to
its 15x cap), then takes the full hit when regime flips. Sharpe dropped from
0.59 to -0.15 at target=0.005/lookback=20 and to 0.52 at target=0.003/lookback=60.
A portfolio-vol overlay is the right idea on a wider universe with more
constant active fractions; it is the wrong layer here.

**OU s-score (audit item #1).** Both as a trigger and as a feature, the
OU s-score regressed in this universe. Its equilibrium estimates are noisy
when the residual is trending, which is exactly when the strategy needs to
gate. The path-z-score implicitly ignores trend, which makes its MR signal
quieter but more reliable.

**Inverse-trend outside tech.** The inverse-trend rule that drives the tech
Sharpe is essentially "fade residual momentum on confirmed (R^2 + volume)
trends." This works in tech but lost in 3 of 5 sectors in the multi-sector
test, with energy and financials particularly bad.

## Backtested Numbers Are Not Out-Of-Sample-Of-The-Researcher

The candidate grid, the universe, the vol-target choice, and the decision to
freeze `enable_ou_score=False` were all guided by inspecting OOS performance
during this work. Treat the Sharpe-0.59 figure as a held-out *single-run*
result against decisions made by the researcher who saw earlier OOS runs.
Honest out-of-sample evaluation of the **current** code requires either
re-running on data after 2025-12-31 or holding out a slice that was not
inspected during the build.

## Related Files Outside This Folder

Theory (lives next to this experiment):

- [`../theory/replication_plan.tex`](../theory/replication_plan.tex) --
  the formal replication specification.
- [`../theory/residual_trend_extension.tex`](../theory/residual_trend_extension.tex)
  -- the formal extension specification (which, empirically, ended up
  implemented as "inverse-trend = fade the residual trend rather than ride
  it"; see Strategy Candidates).
- [`../theory/ssrn-1153505.pdf`](../theory/ssrn-1153505.pdf) -- source paper.

Tools (the framework these scripts compose):

- `research/tools/data/README.md` -- `DataSource` ABC + Cached + ThetaData
  + LayeredPanelSource. The default ingestion path here.
- `research/tools/splits/README.md` -- `WalkForwardSplitter`,
  `NestedWalkForwardSplitter`, `SingleSplitter`, `ExpandingWindowSplitter`.
- `research/tools/metrics/README.md` -- composable `Metric` + `MetricSet`
  wrapping the underlying evaluators.
- `research/tools/backtest/README.md` -- `FactorHedgedDailyBacktestEngine`,
  including the vol-targeting maths.
- `research/tools/strategy/README.md` -- `HybridResidualStrategy` and
  `mr_score_source`.
- `research/tools/transformer/residual_state/README.md` -- the state
  transformer and its optional OU s-score output.
- `research/tools/transformer/mean_reversion/README.md` -- the OU estimator.
- `research/tools/transformer/residualization/README.md` -- the rolling OLS
  beta path used to construct residuals.
- `research/tools/predictor/README.md` -- the per-stock logistic regime
  classifier and label builder.
- `research/tools/evaluation/README.md` -- `BasicStrategyEvaluator` and
  `HybridModeAttributionEvaluator`.
- `research/tools/experiments/README.md` -- the legacy walk-forward planner
  used by older hybrid scripts; the splits package supersedes it for new
  code.
