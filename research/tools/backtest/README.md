# Backtest

This package is for simulation logic.

A backtest engine takes strategy outputs, aligns them with realized returns, and produces realized outcomes such as pnl:

$$
(\text{positions}, \text{realized returns}) \mapsto \text{pnl path}
$$

Examples:

- signal panel $\rightarrow$ lagged positions $\rightarrow$ realized pnl
- target weights + realized returns $\rightarrow$ strategy return series

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/backtest/base.py)

Concrete implementation:

- [factor_hedged.py](factor_hedged.py)
  - `FactorHedgedDailyBacktestEngine`
  - maps daily stock-side OU signals and rolling ETF betas into hedged
    weights with transaction costs, optional per-stock residual-vol-target
    sizing, and optional portfolio-vol target.

## Factor-Hedged Daily PnL

For daily OU or hybrid signals, scores and rolling betas dated $t$ are already
estimated from information ending at $t-1$. `FactorHedgedDailyBacktestEngine`
therefore applies the dated weights directly to return $R_t$ without an
additional lag.

Given stock signal $z_{i,t}$ and base stock allocation $\lambda$, the
**unscaled** stock weight is:

$$
w^{\,base}_{i,t}=\lambda \cdot \mu_{i,t} \cdot z_{i,t},
$$

where $\mu_{i,t}$ is the optional per-stock residual-vol multiplier described
below; with vol targeting disabled, $\mu_{i,t}\equiv 1$.

For factor ETF $f$, the hedge weight is:

$$
w^{\,base}_{f,t}=-\gamma\sum_i w^{\,base}_{i,t}\widehat{\beta}_{i,f,t},
$$

where `hedge_fraction` is $\gamma \in [0,1]$. Setting $\gamma=0$ retains the
residual signal but executes stock positions without ETF compensation;
$\gamma=1$ targets factor-neutral execution. Intermediate values test whether
full neutrality removes useful directional exposure or controls unwanted ETF
exposure. The engine accepts **multiple** factor beta panels — passing one
panel per ETF supports per-sector or multi-factor residualization.

After the optional portfolio-vol scaling step (next section), all stock and
ETF weights are proportionally reduced if their gross exposure exceeds
`gross_exposure_limit`. Net daily portfolio return is:

$$
\pi_t = w_t^\top R_t - c\lVert w_t-w_{t-1}\rVert_1,
$$

where `transaction_cost_bps=5.0` corresponds to $c=0.0005$.

## Optional Volatility Targeting

Both targeting layers are off by default; supplying their target activates
them. They compose multiplicatively.

### Per-Stock Residual-Vol Multiplier

When `residual_volatility_target` is set, `.run(...)` requires a
`residual_volatilities` panel `sigma_{i,t}` with the same index/columns as
`stock_signals`. The per-stock multiplier is:

$$
\mu_{i,t} = \min\!\left(
\frac{\sigma^{\,*}}{\sigma_{i,t}},\;
\mu_{\max}
\right),
$$

where $\sigma^{\,*}$ is `residual_volatility_target` (daily) and $\mu_{\max}$
is `max_position_multiplier` (default 3). The intent is risk parity across
stocks: low-vol names get a larger notional and high-vol names get a smaller
one, so each active position contributes a comparable amount of residual
variance to the portfolio. Multiplier is 0 wherever the signal is 0.

### Portfolio Vol Target

When `portfolio_vol_target` is set, the engine first computes the realized
PnL of the unscaled (post per-stock multiplier and hedge) weights:

$$
\widetilde{\pi}_{t} = \widetilde{w}_t^\top R_t,
$$

then estimates trailing portfolio vol using only rows strictly before $t$
with window `portfolio_vol_lookback`:

$$
\widehat{\sigma}^{\,p}_t
=
\text{std}\!\left(\widetilde{\pi}_{t-\ell-1},\ldots,\widetilde{\pi}_{t-1}\right),
\qquad \ell = \text{portfolio\_vol\_lookback}.
$$

The portfolio-vol scaling is:

$$
\nu_t
=
\min\!\left(
\frac{\sigma^{p,*}}{\widehat{\sigma}^{\,p}_t},\;
\nu_{\max}
\right),
$$

clipped to `max_portfolio_scale` (default 15) and falling back to 1 when
trailing vol is unavailable or zero. Final desired weights are
$\widetilde{w}_t \cdot \nu_t$; the gross-exposure cap is applied last.

The realized `portfolio_vol_scale` per day is exposed in
`exposure_diagnostics`.

### Empirical Note

On the 12-stock tech daily replication, enabling **only** the per-stock
residual-vol multiplier improved the nested-tuning OOS Sharpe from 0.41 to
0.59. Adding the portfolio-vol overlay on top regressed it in every
tested setting because, with a small universe and concentrated active days,
the portfolio scale fires aggressively right at regime transitions. See the
experiment README at `research/experiments/paper_replications/avellaneda_lee_2008/one_day/`
for the full sweep.
