from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from typing import cast

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.modelling.residualization import (
    FactorResidualizationModel,
    FactorSpec,
    OLSExposureEstimator,
)
from research.tools.processing import ReturnsConfig, build_returns


def main() -> None:
    test_date = date(2024, 5, 1)
    factors = ["SPY", "XLK", "QQQ"]
    stocks = ["AAPL", "MSFT", "NVDA"]
    symbols = stocks + factors

    config = ReturnsConfig(horizon="1m", price_source="quote_mid", return_type="log")
    spec = FactorSpec(
        assignments={
            "AAPL": ["SPY", "XLK", "QQQ"],
            "MSFT": ["SPY", "XLK", "QQQ"],
            "NVDA": ["SPY", "XLK", "QQQ"],
        }
    )

    fetcher = ThetaDataFetcher(dataframe_type="pandas")
    try:
        returns = build_returns(config=config, fetcher=fetcher, symbols=symbols, date_=test_date)
    finally:
        close_method = getattr(fetcher.client, "close", None)
        if callable(close_method):
            close_method()

    model = FactorResidualizationModel(spec, OLSExposureEstimator())
    residuals = model.fit_transform(returns)
    exposures = model.exposures

    output_dir = Path("research/temp/residualization_test_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    returns.to_csv(output_dir / "returns_1m.csv")
    residuals.to_csv(output_dir / "residuals_1m.csv")
    exposures.to_csv(output_dir / "exposures.csv")

    print(f"Saved outputs to {output_dir}")
    print("Returns shape:", returns.shape)
    print("Residuals shape:", residuals.shape)
    print("Exposures:")
    print(exposures)
    print("Factor correlation matrix:")
    print(returns[factors].corr())
    factor_matrix = returns[factors].dropna().to_numpy()
    if len(factor_matrix) > 0:
        print("Factor condition number:", float(np.linalg.cond(factor_matrix)))
    print("Per-stock diagnostics:")
    for stock in stocks:
        stock_factors = spec.factors_for(stock)
        y = returns[stock]
        stock_exposures = cast(pd.Series, exposures.loc[stock])
        betas = stock_exposures.reindex(stock_factors)
        if betas.isna().any():
            print(f"{stock}: betas unavailable")
            continue
        explained = returns[stock_factors].mul(betas.to_numpy(), axis=1).sum(axis=1, min_count=1)
        aligned = pd.concat(
            [y.rename("y"), explained.rename("explained"), residuals[stock].rename("residual")] + [returns[f].rename(f) for f in stock_factors],
            axis=1,
        ).dropna()
        if aligned.empty:
            print(f"{stock}: no aligned observations")
            continue
        r2 = 1.0 - float(aligned["residual"].var() / aligned["y"].var()) if float(aligned["y"].var()) > 0 else float("nan")
        residual_corrs = {factor: float(aligned["residual"].corr(aligned[factor])) for factor in stock_factors}
        print(f"{stock}: r2={r2:.4f}, residual_factor_corrs={residual_corrs}")
    print("Residual variance summary:")
    print(residuals.var().sort_values())


if __name__ == "__main__":
    main()
