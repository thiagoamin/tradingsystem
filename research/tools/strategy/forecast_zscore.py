from __future__ import annotations

import numpy as np
import pandas as pd

from research.tools.strategy.base import Strategy


class ForecastZScoreStrategy(Strategy):
    """Position in the direction of unusually large residual forecasts."""

    def __init__(
        self,
        z_window: int = 20,
        entry_z: float = 1.0,
        exit_z: float = 0.25,
        min_hold_bars: int = 1,
        allow_reversal: bool = True,
        invert_signal: bool = False,
    ) -> None:
        if z_window < 2:
            raise ValueError("z_window must be >= 2")
        if entry_z <= 0:
            raise ValueError("entry_z must be > 0")
        if exit_z < 0:
            raise ValueError("exit_z must be >= 0")
        if exit_z >= entry_z:
            raise ValueError("exit_z must be less than entry_z")
        if min_hold_bars < 1:
            raise ValueError("min_hold_bars must be >= 1")
        self.z_window = z_window
        self.entry_z = float(entry_z)
        self.exit_z = float(exit_z)
        self.min_hold_bars = min_hold_bars
        self.allow_reversal = allow_reversal
        self.invert_signal = invert_signal

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Convert residual forecasts into long/short/flat positions."""
        data = -data if self.invert_signal else data
        rolling_mean = data.rolling(window=self.z_window, min_periods=self.z_window).mean()
        rolling_std = data.rolling(window=self.z_window, min_periods=self.z_window).std()
        zscores = (data - rolling_mean).div(rolling_std.replace(0.0, np.nan))
        positions = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        for column in data.columns:
            current = 0.0
            bars_held = 0
            for idx, zscore in zscores[column].items():
                next_position = current
                if np.isnan(zscore):
                    pass
                elif current == 0.0:
                    if zscore >= self.entry_z:
                        next_position = 1.0
                    elif zscore <= -self.entry_z:
                        next_position = -1.0
                elif bars_held < self.min_hold_bars:
                    pass
                elif current > 0.0:
                    if zscore <= -self.entry_z:
                        next_position = -1.0 if self.allow_reversal else 0.0
                    elif zscore <= self.exit_z:
                        next_position = 0.0
                else:
                    if zscore >= self.entry_z:
                        next_position = 1.0 if self.allow_reversal else 0.0
                    elif zscore >= -self.exit_z:
                        next_position = 0.0
                positions.at[idx, column] = next_position
                if next_position == 0.0:
                    bars_held = 0
                elif next_position == current:
                    bars_held += 1
                else:
                    bars_held = 1
                current = next_position
        return positions
