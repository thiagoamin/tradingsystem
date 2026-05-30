# Residual State Transformer

This package builds causal state features from residual-return panels. It is meant to sit after residualization and before a strategy or predictor.

At date $t$, every feature uses information through $t-1$ only. This matches the daily backtest convention where a signal dated $t$ is assumed to be known before return $R_t$ is realized.

For residual returns $\widetilde{R}_{i,t}$, the transformer computes a trailing residual level

$$
X_{i,t}^{(L)} = \sum_{u=t-L}^{t-1} \widetilde{R}_{i,u},
$$

a path-z-score displacement

$$
s^{D}_{i,t}
=
\frac{X_{i,t-1} - \overline{X}_i^{(L)}}{\text{std}\!\left(X_i^{(L)}\right)},
$$

computed over the trailing level window, and a trend score

$$
s^{TR}_{i,t} =
\frac{X_{i,t-1} - X_{i,t-L}}{\widehat{\sigma}_{\widetilde{R},i,t}\sqrt{L}}.
$$

It also uses `sklearn.linear_model.LinearRegression` to estimate the slope and $R^2$ of the trailing residual level. When EOD volume panels are supplied, it adds relative volume and dollar-volume z-score features.

Output is a `ResidualStateResult` containing individual panels and a combined MultiIndex-column feature panel with columns `(symbol, feature)`.

## Optional OU S-Score

Passing an `OUEstimator` via the constructor parameter `ou_estimator` adds two
extra panels to the result:

- `ou_s_score`: the Avellaneda--Lee s-score $(X_{i,t-1}-\widehat m_i)/\widehat\sigma_{eq,i}$,
  fit via AR(1) on the trailing level window.
- `ou_mean_reversion_days`: $\tau = 1/\widehat\kappa$ in trading-day units.

Both panels are also folded into the combined `features` MultiIndex panel so
the regime predictor can consume them alongside `displacement_score`, the
trend score, residual vol, and the volume features. When `ou_estimator=None`
(the default), the panels are `None` and the features panel keeps the original
columns.

The OU s-score is a strict parametric specification: rows where the AR(1)
fit is not stationary (i.e. $b\notin(0,1)$) come out NaN. In the 2020--2025
daily tech panel about 10% of decision dates fail this filter.
