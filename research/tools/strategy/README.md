# Strategy

This package is for trading decision logic.

A strategy takes transformed data, forecasts, or both, and maps them into signals or positions:

$$
\text{model outputs} \mapsto \text{signals or positions}
$$

Examples:

- residual panel $\rightarrow$ mean-reversion signal
- alpha forecast $\rightarrow$ target position
- multiple model outputs $\rightarrow$ combined portfolio weights

This sits after transformation and/or prediction, but before backtesting:

$$
\text{transformer outputs and/or predictor outputs} \rightarrow \text{signals or positions} \rightarrow \text{backtest}
$$

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/base.py)

Concrete strategies:

- [ou_s_score.py](ou_s_score.py)
  - `OUSScoreStrategy`
  - applies the Avellaneda--Lee-style stateful open/close rules to OU s-scores
- [hybrid_residual.py](hybrid_residual.py)
  - `HybridResidualStrategy`
  - chooses residual trend-following, residual mean-reversion, or flat using residual state scores and predicted regime probabilities

## OU S-Score Strategy

`OUSScoreStrategy` consumes the lagged OU s-scores produced by
`RollingOUScoreModel`. For stock-side signal $z_{i,t}\in\{-1,0,+1\}$:

$$
\begin{array}{lll}
z_{i,t}=+1 \text{ from flat} & \text{if} & s_{i,t} < -1.25,\\
z_{i,t}=-1 \text{ from flat} & \text{if} & s_{i,t} > +1.25,\\
z_{i,t}=0 \text{ from short} & \text{if} & s_{i,t} < +0.75,\\
z_{i,t}=0 \text{ from long} & \text{if} & s_{i,t} > -0.50.
\end{array}
$$

A new entry is allowed only when the OU model marks the stock eligible on
that date. If an existing trade receives a valid score but becomes
ineligible, it remains subject to its exit rule; eligibility does not force
liquidation. A missing score closes the trade because no valid current
mean-reversion state is available.

## Hybrid Residual Regime Strategy

`HybridResidualStrategy` consumes `ResidualStateResult` plus a probability
panel $p_{i,t}=P(\text{trend regime})$ from `ResidualRegimePredictor`.

Trend mode opens when:

$$
p_{i,t} \ge p^{TR}_{open}
\quad\text{and}\quad
|s^{TR}_{i,t}| \ge c^{TR}_{open}.
$$

The stock-side trend signal is:

$$
q^{TR}_{i,t}=\operatorname{sign}(s^{TR}_{i,t}).
$$

Mean-reversion mode opens when:

$$
p_{i,t} \le p^{MR}_{open}
\quad\text{and}\quad
|s^{MR}_{i,t}| \ge c^{MR}_{open}.
$$

The stock-side mean-reversion signal is:

$$
q^{MR}_{i,t}=-\operatorname{sign}(s^{MR}_{i,t}).
$$

Optional trend confirmation can require minimum trend-line $R^2$ and minimum
relative volume. The strategy returns a `HybridResidualSignalResult` with:

- `signals`: numeric stock-side signals in `{-1, 0, +1}`
- `modes`: labels `trend`, `mean_reversion`, or `flat`

The strategy does not fit the regime model and does not compute PnL. It only
converts already-computed transformer/predictor outputs into stock-side
trading decisions.

### Choosing The Mean-Reversion Score

The constructor parameter `mr_score_source` selects which panel of the
`ResidualStateResult` is used as $s^{MR}$:

- `"displacement_score"` (default): path z-score of the trailing cumulative
  residual, $(X_{i,t-1} - \overline{X}_i)/\text{std}(X_i)$ over the level
  window. Robust because it makes no parametric assumption.
- `"ou_s_score"`: the Avellaneda--Lee Ornstein--Uhlenbeck s-score
  $(X_{i,t-1}-\widehat m_i)/\widehat\sigma_{eq,i}$. Requires the upstream
  `ResidualStateTransformer` to be configured with an `ou_estimator`; raises
  a `ValueError` otherwise.

The OU s-score is faithful to the source paper but in 2020--2025 tech data
it was empirically inferior to the path-z-score in three settings
(MR trigger only, MR trigger + label, classifier feature). The default
preserves the empirically better choice.
