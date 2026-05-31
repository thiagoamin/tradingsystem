# Contracts

Contracts make pipeline dependencies explicit. A strategy should not rely on
implicit knowledge of loose DataFrames. It should declare the data, variables,
components, and outputs required to train and run.

## Core Objects

- `DataRequirement`: raw or external data dependency. Not limited to market data.
  Use `domain` for `market`, `fundamental`, `macro`, `news`, `portfolio`,
  `broker_state`, or other future sources.
- `VariableSpec`: derived variable dependency such as `daily_returns`,
  `factor_betas`, `spread_bps`, `signed_volume_imbalance`, or
  `regime_probabilities`.
- `ComponentContract`: contract for processors, transformers, predictors,
  strategies, backtests, evaluators, or custom components.
- `StrategyContract`: full declarative dependency contract for one strategy.
- `StrategyRunContext`: concrete runtime data and variables validated against a
  contract.
- `ExperimentContract`: reproducibility contract for one concrete evaluation of
  a strategy: universe, factors, date range, split policy, retraining cadence,
  objective, costs, metrics, and expected artifacts.

## Example

```python
from research.tools.contracts import (
    ComponentContract,
    DataRequirement,
    StrategyContract,
    StrategyRunContext,
    VariableSpec,
)

contract = StrategyContract(
    name="daily_hybrid_residual",
    frequency="1d",
    data_requirements=(
        DataRequirement(
            name="daily_eod",
            domain="market",
            kind="eod",
            source="thetadata",
            fields=("close", "volume"),
            scope="stocks_and_factor_etfs",
        ),
    ),
    variables=(
        VariableSpec(name="daily_returns", role="feature", timing="t_minus_1"),
        VariableSpec(name="rolling_residuals", role="feature", timing="t_minus_1"),
        VariableSpec(name="residual_state_features", role="feature", timing="t_minus_1"),
        VariableSpec(name="regime_target", role="target", timing="t_minus_1"),
        VariableSpec(name="regime_probabilities", role="signal_input", timing="same_time"),
        VariableSpec(name="stock_signals", role="output", timing="same_time"),
    ),
    components=(
        ComponentContract(
            name="residualizer",
            kind="transformer",
            consumes=("daily_returns",),
            produces=("rolling_residuals",),
            fit_required=True,
        ),
        ComponentContract(
            name="regime_predictor",
            kind="predictor",
            consumes_train=("residual_state_features", "regime_target"),
            consumes_inference=("residual_state_features",),
            produces=("regime_probabilities",),
            fit_required=True,
        ),
    ),
    train_variables=("daily_returns", "residual_state_features", "regime_target"),
    inference_variables=("rolling_residuals", "residual_state_features", "regime_probabilities"),
    output_variables=("stock_signals",),
)

ctx = StrategyRunContext(
    data={"daily_eod": eod_panel},
    variables={
        "rolling_residuals": residuals,
        "residual_state_features": features,
        "regime_probabilities": probabilities,
    },
)
ctx.validate(contract, mode="inference")
```

Strategy contracts and experiment contracts intentionally answer different
questions:

- `StrategyContract`: what does this strategy need to train or run?
- `ExperimentContract`: how exactly did we test that strategy?
- `ExperimentRunManifest` in [`../experiments/`](../experiments/) records what
  actually happened after a run: realized folds, retraining, selected params,
  metrics, and artifacts.

```python
from datetime import date

from research.tools.contracts import ExperimentContract

experiment = ExperimentContract(
    name="hybrid_residual_nested_tuning",
    strategy=contract,
    start_date=date(2019, 1, 2),
    end_date=date(2024, 12, 31),
    universe=("AAPL", "MSFT", "NVDA"),
    factors=("XLK",),
    mode="walk_forward",
    horizons=("1d",),
    train_window_days=504,
    test_window_days=63,
    step_days=63,
    retrain_every_n_folds=1,
    selection_objective="sharpe",
    transaction_cost_bps=5.0,
)
```

## Design Rule

Keep contracts declarative. They should validate and document dependencies, not
execute the pipeline. A later runner can use these contracts to resolve a DAG.
