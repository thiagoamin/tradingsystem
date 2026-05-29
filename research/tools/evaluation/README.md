# Evaluation

This package is for post-backtest assessment.

An evaluator takes realized backtest outputs and maps them into summary diagnostics:

$$
\text{realized pnl path} \mapsto \text{performance metrics}
$$

Examples:

- pnl series $\rightarrow$ total return, Sharpe, drawdown
- trade history $\rightarrow$ hit rate, average trade return, turnover

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/base.py)

Concrete implementation:

- [basic.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/basic.py)
  - `BasicStrategyEvaluator`
  - computes cumulative return, mean bar return, bar volatility, Sharpe, max drawdown, hit rate, turnover, average gross exposure, active rate, and position-change count
- [hybrid_attribution.py](/Users/thiagoamin/Desktop/trading_system/research/tools/evaluation/hybrid_attribution.py)
  - `HybridModeAttributionEvaluator`
  - decomposes a factor-hedged hybrid residual backtest into `trend`, `mean_reversion`, and `flat` mode contributions

## Current Metrics

For portfolio PnL $p(t)=\sum_i \text{pnl}_i(t)$:

$$
\text{wealth}(t)=\prod_{u \le t}(1+p(u))
$$

$$
\text{cum\_return}=\text{wealth}(T)-1
$$

$$
\text{sharpe}=\frac{\text{mean}(p)}{\text{std}(p)}
$$

This Sharpe is per-bar unless an `annualization_factor` is provided.

With positions $q_i(t)$, turnover is:

$$
\text{turnover} = \text{mean}_t \sum_i |q_i(t)-q_i(t-1)|
$$

Average gross exposure is:

$$
\text{avg\_gross\_exposure} = \text{mean}_t \sum_i |q_i(t)|
$$

Active rate is the fraction of bars with nonzero gross exposure.

## Hybrid Mode Attribution

`HybridModeAttributionEvaluator` evaluates the hybrid residual strategy after a
factor-hedged backtest has already run. It consumes:

- `FactorHedgedBacktestResult`
- stock-level mode labels from `HybridResidualStrategy`
- factor beta panels used by the backtest

Stock PnL is assigned directly to the stock's contemporaneous mode. If stock
$i$ is in mode $m$ at date $t$, then:

$$
\text{pnl}^{stock}_{m,t}
=
\sum_{i:\text{mode}_{i,t}=m} w_{i,t}R_{i,t}.
$$

ETF hedge PnL is allocated back to modes using each mode's signed contribution
to the hedge. For factor $f$:

$$
h_{m,f,t}
=
-\sum_{i:\text{mode}_{i,t}=m} w_{i,t}\widehat{\beta}_{i,f,t}.
$$

The realized ETF PnL is then assigned by signed contribution share:

$$
\text{pnl}^{hedge}_{m,f,t}
=
\text{pnl}^{hedge}_{f,t}
\frac{h_{m,f,t}}{\sum_{m'}h_{m',f,t}}.
$$

Daily transaction costs are allocated by each mode's share of turnover:

$$
c_{m,t}
=
c_t
\frac{\text{turnover}_{m,t}}
     {\sum_{m'}\text{turnover}_{m',t}}.
$$

The evaluator returns:

- `daily_pnl`: gross PnL, transaction cost, net PnL, and turnover by mode
- `summary`: headline metrics by mode
- `stock_summary`: stock-side activity and PnL by stock/mode
- allocated target weights and asset PnL by mode
