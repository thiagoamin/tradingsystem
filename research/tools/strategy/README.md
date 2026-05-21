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

- [residual_zscore.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/residual_zscore.py)
  - `ResidualZScoreStrategy`
  - builds long/short/flat positions from rolling residual z-scores

Residual strategy with market-variable filters:

- [residual_variable.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/residual_variable.py)
  - `ResidualVariableStrategy`
  - starts from residual z-score mean reversion
  - can require acceptable quoted spread and confirming microprice pressure before entering a trade

Forecast-driven strategy:

- [forecast_zscore.py](/Users/thiagoamin/Desktop/trading_system/research/tools/strategy/forecast_zscore.py)
  - `ForecastZScoreStrategy`
  - trades in the direction of unusually large residual forecasts

## Residual Mean Reversion

For a residual panel $\epsilon_i(t)$, the residual z-score strategy computes:

$$
z_i(t) =
\frac{\epsilon_i(t) - \text{rolling\_mean}_w(\epsilon_i)(t)}
{\text{rolling\_std}_w(\epsilon_i)(t)}
$$

The mean-reversion rule is:

$$
q_i(t) =
\begin{cases}
+1, & z_i(t) \le -z_{\text{entry}} \\
-1, & z_i(t) \ge z_{\text{entry}} \\
0, & |z_i(t)| \le z_{\text{exit}} \text{ after a position is open}
\end{cases}
$$

So a very negative residual enters long, and a very positive residual enters short.

## Residual Variable Filters

`ResidualVariableStrategy` uses the same residual z-score entry rule, but can reject entries using market-state variables.

The spread filter requires:

$$
\text{spread\_bps}_{i,t} \le \text{max\_spread\_bps}
$$

The microprice-pressure filter requires a directional confirmation:

$$
q_i(t)=+1 \Rightarrow \text{microprice\_pressure}_{i,t} \ge \theta
$$

$$
q_i(t)=-1 \Rightarrow \text{microprice\_pressure}_{i,t} \le -\theta
$$

where $\theta$ is `min_abs_microprice_pressure`.

## Forecast Z-Score Strategy

`ForecastZScoreStrategy` consumes a forecast panel $\hat{\epsilon}_i(t+1)$ and z-scores the forecast itself:

$$
z^{\text{forecast}}_i(t) =
\frac{\hat{\epsilon}_i(t+1) - \text{rolling\_mean}_w(\hat{\epsilon}_i)(t)}
{\text{rolling\_std}_w(\hat{\epsilon}_i)(t)}
$$

The direct forecast rule is:

$$
q_i(t) =
\begin{cases}
+1, & z^{\text{forecast}}_i(t) \ge z_{\text{entry}} \\
-1, & z^{\text{forecast}}_i(t) \le -z_{\text{entry}} \\
0, & |z^{\text{forecast}}_i(t)| \le z_{\text{exit}} \text{ after a position is open}
\end{cases}
$$

If `invert_signal=True`, the strategy first maps:

$$
\hat{\epsilon}^{\text{effective}}_i(t+1) = -\hat{\epsilon}_i(t+1)
$$

This turns a forecast-continuation model into a residual-reversal trading signal. The 15-minute state-space experiment currently uses inverted forecast variants because the initial diagnostics showed the profitable sign was opposite the raw forecast.

`min_hold_bars` prevents immediate exits/reversals, and `allow_reversal=False` forces a position to go flat before switching direction.
