# Assigned Sector ETF Replication

This experiment implements the paper's simplified actual-ETF strategy at the
daily horizon using modern ThetaData EOD records.

## Method

Each stock is assigned exactly one traded sector ETF. For a stock $i$ assigned
to ETF $j$, the factor loading is estimated from the trailing 60 daily returns:

$$
\widehat{\beta}_{i,j}
=
\frac{\operatorname{Cov}(R_i,R_{I_j})}
{\operatorname{Var}(R_{I_j})}.
$$

For each decision date $t$, that single trailing-window estimate defines the
residual history used for signal generation:

$$
\widetilde{R}_{i,u}
=
R_{i,u}-\widehat{\beta}_{i,j,t}R_{I_j,u},
\qquad u=t-60,\ldots,t-1.
$$

The cumulative residual is fitted as an OU process. The strategy uses the
paper's pure mean-reversion s-score rule:

$$
\begin{array}{lll}
\text{open long stock / short ETF} & \text{if} & s_i < -1.25,\\
\text{open short stock / long ETF} & \text{if} & s_i > +1.25,\\
\text{close short} & \text{if} & s_i < +0.75,\\
\text{close long} & \text{if} & s_i > -0.50.
\end{array}
$$

Positions are fully ETF-hedged using the current rolling beta, subject to the
gross exposure cap, and charged 5 basis points per dollar of turnover.

## Universe

This is a fixed modern exploratory universe, not the paper's survivorship-free
point-in-time broad equity universe.

| ETF | Stocks |
|---|---|
| `XLK` | `AAPL`, `MSFT`, `NVDA`, `AVGO`, `AMD` |
| `XLF` | `JPM`, `BAC`, `GS`, `MS`, `C` |
| `XLE` | `XOM`, `CVX`, `COP`, `SLB`, `EOG` |
| `XLV` | `LLY`, `JNJ`, `MRK`, `ABBV`, `UNH` |
| `XLI` | `CAT`, `HON`, `UNP`, `UPS`, `LMT` |

`SPY` is also ingested as `MARKET_FACTOR` in `config.py`. It is not used by
this paper-style backtest (no stock is assigned to it as a primary factor) but
is required by the multi-factor residualization variant in
`../multi_sector_hybrid_nested_tuning.py`, which residualizes
`{JPM, BAC, GS, MS, C, XOM, CVX, COP, SLB, EOG}` against `[SPY, sector_ETF]`.
See the parent [experiment README](../README.md#multi-sector-findings) for
the multi-factor result and the per-sector PnL breakdown.

## Run

The initial run downloads the added symbols through ThetaData and stores raw
EOD records. Subsequent runs reuse the derived raw panel unless
`run(refresh_data=True)` is requested explicitly.

```bash
export THETADATA_CREDENTIALS_FILE="$PWD/research/fetchers/thetadata/creds.txt"
/opt/miniconda3/envs/trading_system/bin/python -m research.experiments.paper_replications.avellaneda_lee_2008.one_day.sector_etf.backtest_s_score_strategy
```

The ingestion step applies explicitly configured split corrections and fails
if a remaining daily move is split-like, requiring corporate-action review
before results are accepted. It also writes raw volume, split-adjusted share
volume, and dollar-volume panels when ThetaData volume is present. Dividends
are not currently adjusted.
