# Processing

This package turns raw market data into aligned research panels.

Implementation map:

- [returns_config.py](/Users/thiagoamin/Desktop/trading_system/research/tools/processing/returns_config.py): deterministic return/window choices.
- [returns_builder.py](/Users/thiagoamin/Desktop/trading_system/research/tools/processing/returns_builder.py): horizon-aligned return panels from quote midpoint, last trade, or trade VWAP.
- [quote_variables.py](/Users/thiagoamin/Desktop/trading_system/research/tools/processing/quote_variables.py): quote-derived NBBO variables.
- [trade_variables.py](/Users/thiagoamin/Desktop/trading_system/research/tools/processing/trade_variables.py): trade-derived variables from trade+quote records.
- [residual_features.py](/Users/thiagoamin/Desktop/trading_system/research/tools/processing/residual_features.py): per-symbol predictor features from residuals plus market variables.

The processing layer should not decide positions or PnL. Strategies consume these panels later.

## Quote Variables

For symbol $a$ at bar timestamp $t$, let $b_{a,t}$ be NBBO bid, $a_{a,t}$ be NBBO ask, $B_{a,t}$ be bid size, and $A_{a,t}$ be ask size.

`build_quote_variables(...)` computes:

$$
m_{a,t} = \frac{a_{a,t} + b_{a,t}}{2}
$$

$$
\text{spread\_bps}_{a,t} = 10^4 \frac{a_{a,t} - b_{a,t}}{m_{a,t}}
$$

$$
\text{imbalance}_{a,t} = \frac{B_{a,t} - A_{a,t}}{B_{a,t} + A_{a,t}}
$$

$$
\mu_{a,t} = \frac{a_{a,t}B_{a,t} + b_{a,t}A_{a,t}}{A_{a,t} + B_{a,t}}
$$

$$
\text{microprice\_pressure}_{a,t} = \frac{\mu_{a,t} - m_{a,t}}{a_{a,t} - b_{a,t}}
$$

## Trade Variables

`build_trade_variables(...)` uses ThetaData trade+quote records. Each trade $k$ is signed using the quote midpoint paired to that trade:

$$
\epsilon_{a,k} =
\begin{cases}
+1, & p^T_{a,k} \ge m_{a,\tau_k} \\
-1, & p^T_{a,k} < m_{a,\tau_k}
\end{cases}
$$

For trades in bar window $(t-h,t]$, it computes:

$$
\text{trade\_count}_{a,t,h} = \sum_{k \in T_{a,t,h}} 1
$$

$$
\text{trade\_volume}_{a,t,h} = \sum_{k \in T_{a,t,h}} v^T_{a,k}
$$

$$
\text{dollar\_volume}_{a,t,h} = \sum_{k \in T_{a,t,h}} p^T_{a,k}v^T_{a,k}
$$

$$
\text{VWAP}_{a,t,h} =
\frac{\sum_{k \in T_{a,t,h}} p^T_{a,k}v^T_{a,k}}
{\sum_{k \in T_{a,t,h}} v^T_{a,k}}
$$

$$
\text{SVI}_{a,t,h} =
\frac{\sum_{k \in T_{a,t,h}} \epsilon_{a,k}v^T_{a,k}}
{\sum_{k \in T_{a,t,h}} v^T_{a,k}}
$$

$$
\text{VWAPGap}_{a,t,h} =
\frac{\text{VWAP}_{a,t,h} - m_{a,t}}{m_{a,t}}
$$

In code, these are named `trade_count`, `trade_volume`, `dollar_volume`, `vwap`, `signed_volume_imbalance`, and `vwap_gap`.

## Current Forecast Features

The active 15-minute residual forecast experiment currently uses:

- residual features: `residual`, `residual_mean`, `residual_vol`
- quote variables: `spread_bps`, `imbalance`, `microprice_pressure`
- trade variables: `signed_volume_imbalance`, `vwap_gap`

The processing layer also builds `mid`, `microprice`, `trade_count`, `trade_volume`, `dollar_volume`, and `vwap`, but those are not currently included in the state-space predictor feature set.
