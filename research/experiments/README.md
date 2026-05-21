# Experiments

This folder is for concrete research runs that compose the reusable tools in `research/tools/`.

These scripts are allowed to:

- choose universes, date ranges, and horizons
- define train/test splits
- write output tables and diagnostics
- compare alternative transformers, strategies, backtests, and evaluators

They should not contain reusable core logic that belongs in `research/tools/`.

Current experiment scripts:

- [residual_strategy_6m.py](/Users/thiagoamin/Desktop/trading_system/research/experiments/residual_strategy_6m.py)
  - baseline residual z-score strategy over a walk-forward split.
- [residual_variable_strategy_comparison.py](/Users/thiagoamin/Desktop/trading_system/research/experiments/residual_variable_strategy_comparison.py)
  - compares residual z-score, spread-filtered residual z-score, and spread+microprice residual z-score strategies across fixed horizons.
- [residual_forecast_state_space_15m.py](/Users/thiagoamin/Desktop/trading_system/research/experiments/residual_forecast_state_space_15m.py)
  - compares baseline residual mean reversion against a 15-minute state-space residual forecast strategy.

## Current 15-Minute Forecast Experiment

[residual_forecast_state_space_15m.py](/Users/thiagoamin/Desktop/trading_system/research/experiments/residual_forecast_state_space_15m.py) currently compares:

- `baseline_residual_zscore`
- `state_space_ff0995_e15_hold2_inv`
- `state_space_ff1_e2_hold2_inv`

The forecast models use residualized stock returns plus these market variables:

- quote variables: `spread_bps`, `imbalance`, `microprice_pressure`
- trade variables: `signed_volume_imbalance`, `vwap_gap`

The state-space forecast is inverted before trading. In earlier diagnostics, raw forecast direction was not the profitable trading sign; the inverted versions test residual reversal instead.
