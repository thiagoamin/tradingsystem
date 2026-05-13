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

No concrete predictor has been implemented yet. The base abstraction is:

- [base.py](/Users/thiagoamin/Desktop/trading_system/research/tools/predictor/base.py)
