from __future__ import annotations

"""Backtesting for stock signals accompanied by contemporaneous factor hedges."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FactorHedgedBacktestResult:
    """Portfolio weights, realized PnL, and exposure diagnostics."""

    target_weights: pd.DataFrame
    asset_pnl: pd.DataFrame
    portfolio_pnl: pd.DataFrame
    exposure_diagnostics: pd.DataFrame


class FactorHedgedDailyBacktestEngine:
    """Run a causal daily stock/ETF-hedged backtest with transaction costs.

    Signals and betas dated ``t`` are expected to be available before return
    ``t`` is realized. The engine therefore applies target weights on the same
    dated return row; it does not apply a further position lag.
    """

    def __init__(
        self,
        stock_weight: float = 0.05,
        gross_exposure_limit: float = 2.0,
        transaction_cost_bps: float = 5.0,
        hedge_fraction: float = 1.0,
        residual_volatility_target: float | None = None,
        max_position_multiplier: float = 3.0,
        portfolio_vol_target: float | None = None,
        portfolio_vol_lookback: int = 20,
        max_portfolio_scale: float = 5.0,
    ) -> None:
        """Initialize allocation, gross limit, costs, and optional vol targeting.

        Args:
            stock_weight: Base target allocation per active stock before any
                vol-target rescaling.
            gross_exposure_limit: Maximum gross weight after all scaling.
            transaction_cost_bps: Cost per dollar of changed target weight.
            hedge_fraction: Fraction of estimated factor exposure removed;
                ``0.0`` leaves stock positions unhedged and ``1.0`` targets
                factor neutrality.
            residual_volatility_target: Daily residual-return vol target per
                active stock. When set, ``.run`` requires a ``residual_volatilities``
                panel and scales each active stock by
                ``target / residual_vol_t``, capped at ``max_position_multiplier``.
            max_position_multiplier: Cap on the per-stock vol multiplier; only
                used when ``residual_volatility_target`` is set.
            portfolio_vol_target: Daily portfolio-return vol target. When set,
                the engine rescales desired weights each day by
                ``target / trailing_realized_vol``, using only PnL strictly
                before ``t``. Capped at ``max_portfolio_scale``.
            portfolio_vol_lookback: Trailing window for realized portfolio vol.
            max_portfolio_scale: Cap on the portfolio-level vol multiplier.
        """
        if stock_weight <= 0:
            raise ValueError("stock_weight must be positive")
        if gross_exposure_limit <= 0:
            raise ValueError("gross_exposure_limit must be positive")
        if transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")
        if not 0.0 <= hedge_fraction <= 1.0:
            raise ValueError("hedge_fraction must be between 0.0 and 1.0")
        if residual_volatility_target is not None and residual_volatility_target <= 0:
            raise ValueError("residual_volatility_target must be positive when set")
        if max_position_multiplier <= 0:
            raise ValueError("max_position_multiplier must be positive")
        if portfolio_vol_target is not None and portfolio_vol_target <= 0:
            raise ValueError("portfolio_vol_target must be positive when set")
        if portfolio_vol_lookback < 2:
            raise ValueError("portfolio_vol_lookback must be >= 2")
        if max_portfolio_scale <= 0:
            raise ValueError("max_portfolio_scale must be positive")
        self.stock_weight = float(stock_weight)
        self.gross_exposure_limit = float(gross_exposure_limit)
        self.transaction_cost_rate = float(transaction_cost_bps) / 10_000.0
        self.hedge_fraction = float(hedge_fraction)
        self.residual_volatility_target = (
            float(residual_volatility_target) if residual_volatility_target is not None else None
        )
        self.max_position_multiplier = float(max_position_multiplier)
        self.portfolio_vol_target = (
            float(portfolio_vol_target) if portfolio_vol_target is not None else None
        )
        self.portfolio_vol_lookback = int(portfolio_vol_lookback)
        self.max_portfolio_scale = float(max_portfolio_scale)

    def run(
        self,
        stock_signals: pd.DataFrame,
        returns: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
        residual_volatilities: pd.DataFrame | None = None,
    ) -> FactorHedgedBacktestResult:
        """Compute partially factor-hedged weights and net daily return PnL.

        Args:
            stock_signals: Stock-side signals in ``{-1, 0, 1}``.
            returns: Daily returns containing stock and factor columns.
            factor_betas: Mapping from factor ticker to a beta panel with the
                same index and stock columns as ``stock_signals``.

        Returns:
            Weights, per-asset gross PnL, portfolio net PnL, and exposure
            diagnostics including remaining factor exposure after applying
            ``hedge_fraction``.
        """
        self._validate_inputs(stock_signals, returns, factor_betas)
        per_stock_weights = self._per_stock_weights(stock_signals, residual_volatilities)
        hedge_weights = {
            factor: -self.hedge_fraction * (per_stock_weights * betas).sum(axis=1, min_count=1)
            for factor, betas in factor_betas.items()
        }
        desired = pd.concat([per_stock_weights, pd.DataFrame(hedge_weights)], axis=1).fillna(0.0)
        asset_returns = returns.reindex(index=desired.index, columns=desired.columns)
        portfolio_scale = self._portfolio_vol_scale(desired, asset_returns)
        desired = desired.mul(portfolio_scale, axis=0)

        gross = desired.abs().sum(axis=1)
        scale = (self.gross_exposure_limit / gross).clip(upper=1.0).fillna(1.0)
        target_weights = desired.mul(scale, axis=0)

        missing_active_return = asset_returns.isna() & target_weights.ne(0.0)
        if missing_active_return.any().any():
            raise ValueError("nonzero target weights require complete realized returns")
        asset_pnl = target_weights * asset_returns
        gross_pnl = asset_pnl.sum(axis=1, min_count=1).fillna(0.0)
        turnover = target_weights.diff().fillna(target_weights).abs().sum(axis=1)
        transaction_cost = turnover * self.transaction_cost_rate
        portfolio_pnl = pd.DataFrame(
            {"gross_pnl": gross_pnl, "transaction_cost": transaction_cost, "net_pnl": gross_pnl - transaction_cost}
        )
        diagnostics = self._diagnostics(target_weights, factor_betas, turnover)
        diagnostics["portfolio_vol_scale"] = portfolio_scale
        return FactorHedgedBacktestResult(target_weights, asset_pnl, portfolio_pnl, diagnostics)

    def _per_stock_weights(
        self,
        stock_signals: pd.DataFrame,
        residual_volatilities: pd.DataFrame | None,
    ) -> pd.DataFrame:
        if self.residual_volatility_target is None:
            return stock_signals * self.stock_weight
        if residual_volatilities is None:
            raise ValueError(
                "residual_volatilities is required when residual_volatility_target is set"
            )
        vol = residual_volatilities.reindex(index=stock_signals.index, columns=stock_signals.columns)
        missing_active_vol = vol.isna() & stock_signals.ne(0.0)
        if missing_active_vol.any().any():
            raise ValueError("active stock signals require complete residual_volatilities")
        positive_vol = vol.where(vol > 0.0)
        multiplier = (self.residual_volatility_target / positive_vol).clip(
            upper=self.max_position_multiplier
        )
        multiplier = multiplier.where(stock_signals.ne(0.0), 0.0).fillna(0.0)
        return stock_signals * self.stock_weight * multiplier

    def _portfolio_vol_scale(
        self,
        desired: pd.DataFrame,
        asset_returns: pd.DataFrame,
    ) -> pd.Series:
        if self.portfolio_vol_target is None:
            return pd.Series(1.0, index=desired.index)
        usable_returns = asset_returns.where(desired.ne(0.0), 0.0).fillna(0.0)
        pre_pnl = (desired * usable_returns).sum(axis=1, min_count=1).fillna(0.0)
        min_periods = max(5, self.portfolio_vol_lookback // 2)
        trailing_vol = (
            pre_pnl.shift(1).rolling(self.portfolio_vol_lookback, min_periods=min_periods).std()
        )
        safe_vol = trailing_vol.where(trailing_vol > 0.0)
        scale = (self.portfolio_vol_target / safe_vol).clip(upper=self.max_portfolio_scale)
        return scale.fillna(1.0)

    def _validate_inputs(
        self,
        stock_signals: pd.DataFrame,
        returns: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
    ) -> None:
        if stock_signals.empty:
            raise ValueError("stock_signals must be non-empty")
        if not factor_betas:
            raise ValueError("factor_betas must be non-empty")
        if set(stock_signals.columns) & set(factor_betas):
            raise ValueError("stock and factor symbols must not overlap")
        required = set(stock_signals.columns) | set(factor_betas)
        missing = sorted(required - set(returns.columns))
        if missing:
            raise ValueError(f"returns is missing required stock/factor columns: {missing}")
        for factor, betas in factor_betas.items():
            if not stock_signals.index.equals(betas.index):
                raise ValueError(f"beta panel for '{factor}' must share stock_signals index")
            if list(stock_signals.columns) != list(betas.columns):
                raise ValueError(f"beta panel for '{factor}' must share stock_signals columns")
            missing_active_beta = betas.isna() & stock_signals.ne(0.0)
            if missing_active_beta.any().any():
                raise ValueError(f"active stock signals require complete beta values for factor '{factor}'")

    @staticmethod
    def _diagnostics(
        weights: pd.DataFrame,
        factor_betas: dict[str, pd.DataFrame],
        turnover: pd.Series,
    ) -> pd.DataFrame:
        stocks = list(next(iter(factor_betas.values())).columns)
        factors = list(factor_betas)
        output = pd.DataFrame(index=weights.index)
        output["long_gross"] = weights.clip(lower=0.0).sum(axis=1)
        output["short_gross"] = -weights.clip(upper=0.0).sum(axis=1)
        output["stock_gross"] = weights[stocks].abs().sum(axis=1)
        output["hedge_gross"] = weights[factors].abs().sum(axis=1)
        output["gross_exposure"] = output["stock_gross"] + output["hedge_gross"]
        output["net_exposure"] = weights.sum(axis=1)
        output["turnover"] = turnover
        for factor, betas in factor_betas.items():
            output[f"net_{factor}_exposure"] = (weights[stocks] * betas).sum(axis=1) + weights[factor]
        return output
