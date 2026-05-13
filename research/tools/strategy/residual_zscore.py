from __future__ import annotations

import numpy as np
import pandas as pd

from research.tools.strategy.base import Strategy


class ResidualZScoreStrategy(Strategy):
    """Mean-reversion strategy based on rolling residual z-scores."""

    def __init__(self, z_window: int = 60, entry_z: float = 2.0, exit_z: float = 0.5) -> None:
        if z_window < 2:
            raise ValueError("z_window must be >= 2")
        if entry_z <= 0:
            raise ValueError("entry_z must be > 0")
        if exit_z < 0:
            raise ValueError("exit_z must be >= 0")
        if exit_z >= entry_z:
            raise ValueError("exit_z must be less than entry_z")
        self.z_window = z_window
        self.entry_z = float(entry_z)
        self.exit_z = float(exit_z)

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Convert residual returns into long/short/flat positions."""
        rolling_mean = data.rolling(window=self.z_window, min_periods=self.z_window).mean()
        rolling_std = data.rolling(window=self.z_window, min_periods=self.z_window).std()
        zscores = (data - rolling_mean).div(rolling_std.replace(0.0, np.nan))
        positions = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        for column in data.columns:
            current = 0.0
            for idx, zscore in zscores[column].items():
                if np.isnan(zscore):
                    positions.at[idx, column] = current
                    continue
                if current == 0.0:
                    if zscore <= -self.entry_z:
                        current = 1.0
                    elif zscore >= self.entry_z:
                        current = -1.0
                elif current > 0.0:
                    if zscore >= self.entry_z:
                        current = -1.0
                    elif zscore >= -self.exit_z:
                        current = 0.0
                else:
                    if zscore <= -self.entry_z:
                        current = 1.0
                    elif zscore <= self.exit_z:
                        current = 0.0
                positions.at[idx, column] = current
        return positions
