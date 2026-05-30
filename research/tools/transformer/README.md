# Transformer

This package holds modelling components that transform one panel into another:

$$
X \mapsto \tilde{X}
$$

A transformer does not forecast the future. It changes the representation of the current or historical data.

Its output can be used directly by a strategy or passed into a predictor first.

Examples:

- returns $\rightarrow$ residual returns
- returns $\rightarrow$ volatility-scaled returns
- returns $\rightarrow$ normalized returns

Implemented transformers:

- [residualization/](/Users/thiagoamin/Desktop/trading_system/research/tools/transformer/residualization)
  - returns to factor-residual returns, including rolling ETF residual paths.
- [mean_reversion/](/Users/thiagoamin/Desktop/trading_system/research/tools/transformer/mean_reversion)
  - residual returns to rolling OU parameter, eligibility, and s-score paths.
- [residual_state/](/Users/thiagoamin/Desktop/trading_system/research/tools/transformer/residual_state)
  - residual returns plus optional volume panels to causal displacement, trend, volatility, and liquidity state features; optionally also rolling OU s-score and mean-reversion-time panels when an `OUEstimator` is supplied.
