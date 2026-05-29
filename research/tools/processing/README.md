# Processing

This package turns raw market data into aligned research panels. The active
surface is daily EOD; the intraday processing previously here has been
removed along with the experiments that consumed it.

## Implementation map

- [corporate_actions.py](corporate_actions.py): explicit stock-split
  adjustment factors for raw daily close panels.
- [daily_eod.py](daily_eod.py): daily ThetaData EOD raw/split-adjusted
  close, volume, dollar-volume, and stock/ETF return panels for daily
  residual models.

The processing layer does not decide positions or PnL; the
[`backtest/`](../backtest/) layer does.

## Daily EOD Price And Volume

`build_daily_eod_panels(...)` consumes long records from the ThetaData EOD
ingestion layer, optionally applies a supplied schedule of verified stock
splits, and separates modeled stock returns from factor-ETF returns. For raw
close $S_{i,t}$, raw share volume $V_{i,t}$, and split adjustment factor
$A_{i,t}$, the modelling close is:

$$
\widetilde{S}_{i,t} = A_{i,t} S_{i,t}.
$$

For a forward split of ratio $k$ effective at date $d$, the factor applied to
prior raw closes is $1/k$. Share volume is adjusted in the opposite direction
so price and volume live on the same share basis:

$$
\widetilde{V}_{i,t} = \frac{V_{i,t}}{A_{i,t}}.
$$

The dollar-volume panel is then:

$$
\widetilde{D}_{i,t} = \widetilde{S}_{i,t}\widetilde{V}_{i,t}.
$$

This equals raw close times raw volume when the only adjustment is a stock
split. The returned log return is:

$$
R_{i,t} = \log\left(\frac{\widetilde{S}_{i,t}}{\widetilde{S}_{i,t-1}}\right).
$$

The upstream source is `ThetaClient.stock_history_eod(...)`, exposed through
[`research/fetchers/thetadata/theta_fetcher.py`](../../fetchers/thetadata/theta_fetcher.py)
and [`theta_eod_ingestor.py`](../../fetchers/thetadata/theta_eod_ingestor.py).
The installed ThetaData Python EOD interface supplies OHLCV/BBO records but
no declared split/dividend-adjusted close field. The daily replication
supplies an explicit audited split schedule for discontinuities present in
the raw panel. Cash dividends remain unadjusted, so this is a split-adjusted
price return panel rather than a full total-return panel.

## Stock-Split Adjustment

`apply_stock_split_adjustments(closes, split_events)` returns the
split-adjusted closes plus the per-symbol-per-date adjustment factor matrix.
`build_split_adjustment_factors(closes, split_events)` returns just the
factors; this is what `build_daily_eod_panels` calls internally.

Split events are passed as `tuple[StockSplit, ...]`, each `StockSplit` having
`symbol`, `effective_date`, `ratio`, and a free-text `source` URL for audit.
The daily replication's hand-curated schedule lives in
[`research/experiments/paper_replications/avellaneda_lee_2008/one_day/configured_splits.py`](../../experiments/paper_replications/avellaneda_lee_2008/one_day/configured_splits.py).

## Typical caller

`build_daily_eod_panels` is the only public entry point most users need; it
is invoked by both data sources in [`../data/`](../data/) and is what
materializes the on-disk panel cache.
