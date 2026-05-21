# Predictor

This package is for forecasting models.

A predictor maps panel features to predicted outputs:

$$
X \mapsto \hat{Y}
$$

Examples:

- residual features $\rightarrow$ next residual return forecast
- feature panel $\rightarrow$ probability of positive return
- feature panel $\rightarrow$ expected spread reversion

A predictor can consume transformed outputs, raw processed features, or both. It sits before strategy when a forecasting step is part of the workflow.

The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/predictor/base.py)

Concrete predictors:

- [state_space.py](/Users/thiagoamin/Desktop/trading_system/research/tools/predictor/state_space.py)
  - `RecursiveLeastSquaresResidualPredictor`
  - forecasts next-bar residual returns with a state-space style recursive linear model
  - uses a forgetting factor so recent observations receive more weight

## Recursive Least Squares Residual Forecast

For stock $i$, the predictor uses features $x_i(t)$ known at bar $t$ to forecast the next residual:

$$
\hat{\epsilon}_i(t+1) = \beta_{i,0} + x_i(t)^\top \beta_i
$$

The active 15-minute experiment uses:

$$
x_i(t) =
[
\epsilon_i(t),
\text{rolling\_mean}(\epsilon_i)(t),
\text{rolling\_vol}(\epsilon_i)(t),
\text{spread\_bps}_i(t),
\text{imbalance}_i(t),
\text{microprice\_pressure}_i(t),
\text{signed\_volume\_imbalance}_i(t),
\text{vwap\_gap}_i(t)
]
$$

The coefficient vector is updated recursively during `fit(...)`. With forgetting factor $\lambda$, covariance matrix $P_t$, and feature row $\tilde{x}_t = [1, x_t]$, the update is:

$$
K_t = \frac{P_{t-1}\tilde{x}_t}{\lambda + \tilde{x}_t^\top P_{t-1}\tilde{x}_t}
$$

$$
\beta_t = \beta_{t-1} + K_t(y_t - \tilde{x}_t^\top\beta_{t-1})
$$

$$
P_t = \frac{P_{t-1} - K_t\tilde{x}_t^\top P_{t-1}}{\lambda}
$$

where $y_t=\epsilon_i(t+1)$ during fitting.

During `predict(...)`, coefficients are fixed. The model does not update on test data, so walk-forward test predictions remain out of sample.
