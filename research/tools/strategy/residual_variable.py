from __future__ import annotations

import numpy as np
import pandas as pd

from research.tools.strategy.base import Strategy

QuoteVariablePanels = dict[str, pd.DataFrame]


class ResidualVariableStrategy(Strategy):
    """Residual mean-reversion strategy with optional quote-variable entry filters."""

    def __init__(
        self,
        z_window: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        max_spread_bps: float | None = None,
        min_abs_microprice_pressure: float | None = None,
    ) -> None:
        if z_window < 2:
            raise ValueError("z_window must be >= 2")
        if entry_z <= 0:
            raise ValueError("entry_z must be > 0")
        if exit_z < 0:
            raise ValueError("exit_z must be >= 0")
        if exit_z >= entry_z:
            raise ValueError("exit_z must be less than entry_z")
        if max_spread_bps is not None and max_spread_bps <= 0:
            raise ValueError("max_spread_bps must be > 0 when provided")
        if min_abs_microprice_pressure is not None and min_abs_microprice_pressure < 0:
            raise ValueError("min_abs_microprice_pressure must be >= 0 when provided")

        self.z_window = z_window
        self.entry_z = float(entry_z)
        self.exit_z = float(exit_z)
        self.max_spread_bps = max_spread_bps
        self.min_abs_microprice_pressure = min_abs_microprice_pressure

    def generate(self, data: pd.DataFrame, variables: QuoteVariablePanels | None = None) -> pd.DataFrame:
        """Convert residual returns into positions, optionally filtered by quote variables."""
        rolling_mean = data.rolling(window=self.z_window, min_periods=self.z_window).mean()
        rolling_std = data.rolling(window=self.z_window, min_periods=self.z_window).std()
        zscores = (data - rolling_mean).div(rolling_std.replace(0.0, np.nan))
        spread_bps = self._optional_variable("spread_bps", variables, data)
        microprice_pressure = self._optional_variable("microprice_pressure", variables, data)

        positions = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        for column in data.columns:
            current = 0.0
            for idx, zscore in zscores[column].items():
                if np.isnan(zscore):
                    positions.at[idx, column] = current
                    continue
                if current == 0.0:
                    if zscore <= -self.entry_z and self._entry_allowed(idx, column, 1.0, spread_bps, microprice_pressure):
                        current = 1.0
                    elif zscore >= self.entry_z and self._entry_allowed(idx, column, -1.0, spread_bps, microprice_pressure):
                        current = -1.0
                elif current > 0.0:
                    if zscore >= self.entry_z and self._entry_allowed(idx, column, -1.0, spread_bps, microprice_pressure):
                        current = -1.0
                    elif zscore >= -self.exit_z:
                        current = 0.0
                else:
                    if zscore <= -self.entry_z and self._entry_allowed(idx, column, 1.0, spread_bps, microprice_pressure):
                        current = 1.0
                    elif zscore <= self.exit_z:
                        current = 0.0
                positions.at[idx, column] = current
        return positions

    def _optional_variable(
        self,
        name: str,
        variables: QuoteVariablePanels | None,
        data: pd.DataFrame,
    ) -> pd.DataFrame | None:
        if name == "spread_bps" and self.max_spread_bps is None:
            return None
        if name == "microprice_pressure" and self.min_abs_microprice_pressure is None:
            return None
        if variables is None or name not in variables:
            raise ValueError(f"variables must include '{name}' for this strategy configuration")
        return variables[name].reindex(index=data.index, columns=data.columns)

    def _entry_allowed(
        self,
        idx: object,
        column: str,
        direction: float,
        spread_bps: pd.DataFrame | None,
        microprice_pressure: pd.DataFrame | None,
    ) -> bool:
        if spread_bps is not None:
            spread_value = float(spread_bps.at[idx, column])
            if np.isnan(spread_value) or spread_value > float(self.max_spread_bps):
                return False
        if microprice_pressure is not None:
            pressure = float(microprice_pressure.at[idx, column])
            if np.isnan(pressure):
                return False
            threshold = float(self.min_abs_microprice_pressure)
            if direction > 0 and pressure < threshold:
                return False
            if direction < 0 and pressure > -threshold:
                return False
        return True
