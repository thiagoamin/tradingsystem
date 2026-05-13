# Transformer

This package holds modelling components that transform one panel into another:

$$
X \mapsto \tilde{X}
$$

A transformer does not forecast the future. It changes the representation of the current or historical data.

Examples:

- returns $\rightarrow$ residual returns
- returns $\rightarrow$ volatility-scaled returns
- returns $\rightarrow$ normalized returns

The main implemented transformer so far is residualization, located in:

- [residualization/](/Users/thiagoamin/Desktop/trading_system/research/tools/transformer/residualization)
