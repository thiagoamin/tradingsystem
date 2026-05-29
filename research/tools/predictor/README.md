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

- [regime.py](regime.py)
  - `ResidualRegimePredictor`
  - estimates whether residual trend-following or residual mean-reversion would be favored
  - uses sklearn classifiers; the default is scaled logistic regression

## Residual Regime Forecast

The regime predictor is used after residual state construction. For stock $i$
at date $t$, define:

$$
d^{TR}_{i,t} = \operatorname{sign}(s^{TR}_{i,t})
$$

as the trend-following residual direction, and

$$
d^{MR}_{i,t} = -\operatorname{sign}(s^{MR}_{i,t})
$$

as the mean-reversion residual direction, where $s^{MR}$ can be represented by
the residual displacement score. The training label is:

$$
y_{i,t} =
\begin{cases}
1, & d^{TR}_{i,t}\widetilde{R}_{i,t}
     >
     d^{MR}_{i,t}\widetilde{R}_{i,t} + m,\\
0, & d^{MR}_{i,t}\widetilde{R}_{i,t}
     >
     d^{TR}_{i,t}\widetilde{R}_{i,t} + m,\\
\text{missing}, & \text{otherwise}.
\end{cases}
$$

Here $m \ge 0$ is an optional payoff margin. The model predicts
$P(y_{i,t}=1 \mid x_{i,t})$, the probability that the residual trend direction
is preferable to the residual mean-reversion direction. The default estimator is
`sklearn.pipeline(StandardScaler, LogisticRegression)` with balanced class
weights. Strategies can later threshold this probability to choose trend,
mean-reversion, or flat mode.
