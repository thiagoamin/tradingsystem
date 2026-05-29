from __future__ import annotations

"""Mode attribution for hybrid residual strategy backtests."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.tools.backtest import FactorHedgedBacktestResult
from research.tools.evaluation.basic import BasicStrategyEvaluator

DEFAULT_MODES = ("trend", "mean_reversion", "flat")


@dataclass(frozen=True)
class ModeAttributionResult:
    """Hybrid-strategy PnL and activity split by trading mode.

    Attributes:
        daily_pnl: MultiIndex-column panel ``(mode, metric)`` with gross PnL,
            transaction cost, net PnL, and turnover by mode.
        summary: One row per mode with headline performance and activity metrics.
        stock_summary: One row per stock/mode with stock-side activity and PnL.
        target_weights_by_mode: Target weights allocated to each mode.
        asset_pnl_by_mode: Asset gross PnL allocated to each mode.
    """

    daily_pnl: pd.DataFrame
    summary: pd.DataFrame
    stock_summary: pd.DataFrame
    target_weights_by_mode: dict[str, pd.DataFrame]
    asset_pnl_by_mode: dict[str, pd.DataFrame]


class HybridModeAttributionEvaluator:
    """Attribute a factor-hedged hybrid residual backtest by strategy mode.

    Stock PnL is attributed to the contemporaneous stock mode. ETF hedge PnL is
    attributed by the mode's signed contribution to the ETF hedge on that date.
    Daily transaction costs are allocated by each mode's share of turnover.
    """

    def __init__(self, annualization_factor: float | None = 252, modes: tuple[str, ...] = DEFAULT_MODES) -> None:
        """Initialize summary evaluator settings.

        Args:
            annualization_factor: Optional annualization factor for Sharpe ratios.
            modes: Mode labels to report. Defaults to trend, mean_reversion, flat.

        Raises:
            ValueError: If no modes are supplied.
        """
        if not modes:
            raise ValueError("modes must be non-empty")
        self.modes = tuple(modes)
        self.basic_evaluator = BasicStrategyEvaluator(annualization_factor=annualization_factor)

    def evaluate(
        self,
        backtest_result: FactorHedgedBacktestResult,
        modes: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
    ) -> ModeAttributionResult:
        """Compute mode-level attribution for a factor-hedged backtest.

        Args:
            backtest_result: Output from ``FactorHedgedDailyBacktestEngine``.
            modes: Stock-mode labels aligned to the stock signal panel.
            factor_betas: Factor beta panels used in the backtest.

        Returns:
            Daily PnL, performance summary, stock summary, and allocated weights/PnL.

        Raises:
            ValueError: If modes, weights, PnL, or beta panels cannot align.
        """
        self._validate_inputs(backtest_result, modes, factor_betas)
        stocks = list(modes.columns)
        factors = list(factor_betas)
        modes = modes.reindex(index=backtest_result.target_weights.index, columns=stocks).fillna("flat")

        target_weights_by_mode = self._target_weights_by_mode(backtest_result, modes, factor_betas, stocks, factors)
        asset_pnl_by_mode = self._asset_pnl_by_mode(backtest_result, modes, target_weights_by_mode, stocks, factors)
        daily_pnl = self._daily_pnl(backtest_result, target_weights_by_mode, asset_pnl_by_mode)
        summary = self._summary(daily_pnl, target_weights_by_mode)
        stock_summary = self._stock_summary(backtest_result, modes, stocks)
        return ModeAttributionResult(daily_pnl, summary, stock_summary, target_weights_by_mode, asset_pnl_by_mode)

    def _target_weights_by_mode(
        self,
        result: FactorHedgedBacktestResult,
        modes: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
        stocks: list[str],
        factors: list[str],
    ) -> dict[str, pd.DataFrame]:
        output: dict[str, pd.DataFrame] = {}
        stock_weights = result.target_weights.loc[:, stocks]
        for mode in self.modes:
            mode_stock_weights = stock_weights.where(modes.eq(mode), 0.0)
            output[mode] = mode_stock_weights.copy()

        for factor in factors:
            raw_contrib = pd.DataFrame(index=stock_weights.index)
            betas = factor_betas[factor].reindex(index=stock_weights.index, columns=stocks)
            for mode in self.modes:
                raw_contrib[mode] = -(output[mode].loc[:, stocks] * betas).sum(axis=1)
            total_raw = raw_contrib.sum(axis=1)
            actual_factor_weight = result.target_weights[factor]
            shares = raw_contrib.div(total_raw.replace(0.0, np.nan), axis=0).fillna(0.0)
            for mode in self.modes:
                output[mode][factor] = actual_factor_weight * shares[mode]
        return output

    def _asset_pnl_by_mode(
        self,
        result: FactorHedgedBacktestResult,
        modes: pd.DataFrame,
        target_weights_by_mode: dict[str, pd.DataFrame],
        stocks: list[str],
        factors: list[str],
    ) -> dict[str, pd.DataFrame]:
        output: dict[str, pd.DataFrame] = {}
        for mode in self.modes:
            mode_pnl = pd.DataFrame(0.0, index=result.asset_pnl.index, columns=stocks + factors)
            mode_pnl.loc[:, stocks] = result.asset_pnl.loc[:, stocks].where(modes.eq(mode), 0.0)
            output[mode] = mode_pnl

        for factor in factors:
            raw_factor_weights = pd.DataFrame({mode: target_weights_by_mode[mode][factor] for mode in self.modes})
            total_weight = raw_factor_weights.sum(axis=1)
            shares = raw_factor_weights.div(total_weight.replace(0.0, np.nan), axis=0).fillna(0.0)
            for mode in self.modes:
                output[mode][factor] = result.asset_pnl[factor] * shares[mode]
        return output

    def _daily_pnl(
        self,
        result: FactorHedgedBacktestResult,
        target_weights_by_mode: dict[str, pd.DataFrame],
        asset_pnl_by_mode: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        turnover = pd.DataFrame(
            {
                mode: weights.diff().fillna(weights).abs().sum(axis=1)
                for mode, weights in target_weights_by_mode.items()
            }
        )
        total_mode_turnover = turnover.sum(axis=1)
        transaction_cost = pd.DataFrame(0.0, index=result.portfolio_pnl.index, columns=self.modes)
        actual_cost = result.portfolio_pnl["transaction_cost"]
        for mode in self.modes:
            share = turnover[mode].div(total_mode_turnover.replace(0.0, np.nan)).fillna(0.0)
            transaction_cost[mode] = actual_cost * share

        blocks: dict[str, pd.DataFrame] = {}
        for mode in self.modes:
            gross = asset_pnl_by_mode[mode].sum(axis=1).fillna(0.0)
            cost = transaction_cost[mode]
            blocks[mode] = pd.DataFrame(
                {
                    "gross_pnl": gross,
                    "transaction_cost": cost,
                    "net_pnl": gross - cost,
                    "turnover": turnover[mode],
                }
            )
        return pd.concat(blocks, axis=1)

    def _summary(self, daily_pnl: pd.DataFrame, target_weights_by_mode: dict[str, pd.DataFrame]) -> pd.DataFrame:
        rows: list[dict[str, float | str]] = []
        for mode in self.modes:
            pnl = daily_pnl[(mode, "net_pnl")]
            positions = target_weights_by_mode[mode]
            metrics = self.basic_evaluator.evaluate(pnl, positions=positions)
            active = positions.abs().sum(axis=1) > 0.0
            active_pnl = pnl.loc[active]
            rows.append(
                {
                    "mode": mode,
                    **metrics,
                    "gross_pnl_sum": float(daily_pnl[(mode, "gross_pnl")].sum()),
                    "transaction_cost_sum": float(daily_pnl[(mode, "transaction_cost")].sum()),
                    "net_pnl_sum": float(pnl.sum()),
                    "active_observations": int(active.sum()),
                    "active_hit_rate": float((active_pnl > 0.0).mean()) if not active_pnl.empty else float("nan"),
                }
            )
        return pd.DataFrame(rows)

    def _stock_summary(self, result: FactorHedgedBacktestResult, modes: pd.DataFrame, stocks: list[str]) -> pd.DataFrame:
        rows: list[dict[str, float | str | int]] = []
        for stock in stocks:
            stock_pnl = result.asset_pnl[stock]
            stock_weight = result.target_weights[stock]
            for mode in self.modes:
                active = modes[stock].eq(mode) & stock_weight.ne(0.0)
                mode_pnl = stock_pnl.where(active, 0.0)
                rows.append(
                    {
                        "symbol": stock,
                        "mode": mode,
                        "active_days": int(active.sum()),
                        "long_days": int((active & stock_weight.gt(0.0)).sum()),
                        "short_days": int((active & stock_weight.lt(0.0)).sum()),
                        "gross_pnl_sum": float(mode_pnl.sum()),
                        "avg_active_pnl": float(stock_pnl.loc[active].mean()) if active.any() else float("nan"),
                    }
                )
        return pd.DataFrame(rows)

    def _validate_inputs(
        self,
        result: FactorHedgedBacktestResult,
        modes: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
    ) -> None:
        if modes.empty:
            raise ValueError("modes must be non-empty")
        if not factor_betas:
            raise ValueError("factor_betas must be non-empty")
        stocks = list(modes.columns)
        factors = list(factor_betas)
        required = set(stocks) | set(factors)
        missing_weights = sorted(required - set(result.target_weights.columns))
        missing_pnl = sorted(required - set(result.asset_pnl.columns))
        if missing_weights:
            raise ValueError(f"target_weights is missing required columns: {missing_weights}")
        if missing_pnl:
            raise ValueError(f"asset_pnl is missing required columns: {missing_pnl}")
        observed_modes = set(modes.stack().dropna().astype(str))
        missing_modes = sorted(observed_modes - set(self.modes))
        if missing_modes:
            raise ValueError(f"modes contains unsupported labels: {missing_modes}")
        for factor, betas in factor_betas.items():
            if not result.target_weights.index.equals(betas.index):
                raise ValueError(f"beta panel for '{factor}' must share backtest index")
            if list(betas.columns) != stocks:
                raise ValueError(f"beta panel for '{factor}' must share mode stock columns")
