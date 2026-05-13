from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from research.fetchers.thetadata import ThetaDataFetcher
from research.tools.transformer.residualization import (
    ElasticNetExposureEstimator,
    FactorResidualizationModel,
    FactorSpec,
    OLSExposureEstimator,
    RidgeExposureEstimator,
)
from research.tools.processing import ReturnsConfig, build_returns


def _business_days(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _build_multi_day_returns(
    fetcher: ThetaDataFetcher, config: ReturnsConfig, symbols: list[str], start_date: date, end_date: date
) -> pd.DataFrame:
    daily_frames: list[pd.DataFrame] = []
    for trading_date in _business_days(start_date, end_date):
        daily_returns = build_returns(config=config, fetcher=fetcher, symbols=symbols, date_=trading_date)
        if not daily_returns.empty:
            daily_frames.append(daily_returns)
    if not daily_frames:
        raise ValueError("No return data was fetched for the requested date range.")
    return pd.concat(daily_frames).sort_index()


def _summarize_model(
    name: str, model: FactorResidualizationModel, returns: pd.DataFrame, spec: FactorSpec, stocks: list[str], factors: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    residuals = model.fit_transform(returns)
    exposures = model.exposures
    summary_rows: list[dict[str, float | str]] = []
    for stock in stocks:
        stock_factors = spec.factors_for(stock)
        y = returns[stock]
        stock_exposures = cast(pd.Series, exposures.loc[stock])
        betas = stock_exposures.reindex(stock_factors)
        if betas.isna().any():
            summary_rows.append({"model": name, "stock": stock, "r2": np.nan, "residual_variance": np.nan})
            continue
        explained = returns[stock_factors].mul(betas.to_numpy(), axis=1).sum(axis=1, min_count=1)
        aligned = pd.concat(
            [y.rename("y"), explained.rename("explained"), residuals[stock].rename("residual")] + [returns[f].rename(f) for f in stock_factors],
            axis=1,
        ).dropna()
        if aligned.empty:
            summary_rows.append({"model": name, "stock": stock, "r2": np.nan, "residual_variance": np.nan})
            continue
        y_var = float(aligned["y"].var())
        residual_var = float(aligned["residual"].var())
        r2 = 1.0 - residual_var / y_var if y_var > 0 else float("nan")
        row: dict[str, float | str] = {"model": name, "stock": stock, "r2": r2, "residual_variance": residual_var}
        for factor in factors:
            row[f"corr_resid_{factor}"] = float(aligned["residual"].corr(aligned[factor]))
        summary_rows.append(row)
    return residuals, exposures, pd.DataFrame(summary_rows)


def main() -> None:
    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 3)
    factors = ["SPY", "XLK", "QQQ"]
    stocks = ["AAPL", "MSFT", "NVDA"]
    symbols = stocks + factors
    config = ReturnsConfig(horizon="1m", price_source="quote_mid", return_type="log")
    spec = FactorSpec({stock: factors for stock in stocks})

    fetcher = ThetaDataFetcher(dataframe_type="pandas")
    try:
        returns = _build_multi_day_returns(fetcher, config, symbols, start_date, end_date)
    finally:
        close_method = getattr(fetcher.client, "close", None)
        if callable(close_method):
            close_method()

    models = {
        "ols": FactorResidualizationModel(spec, OLSExposureEstimator()),
        "ridge": FactorResidualizationModel(spec, RidgeExposureEstimator(alpha=1.0)),
        "elastic_net": FactorResidualizationModel(spec, ElasticNetExposureEstimator(alpha=0.1, l1_ratio=0.5)),
    }

    output_dir = Path("research/temp/residualization_test_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    returns.to_csv(output_dir / "returns_1m_multi_day.csv")

    factor_corr = returns[factors].corr()
    factor_matrix = returns[factors].dropna().to_numpy()
    factor_condition_number = float(np.linalg.cond(factor_matrix)) if len(factor_matrix) > 0 else float("nan")

    summary_frames: list[pd.DataFrame] = []
    print(f"Saved outputs to {output_dir}")
    print(f"Date range: {start_date} to {end_date}")
    print("Returns shape:", returns.shape)
    print("Factor correlation matrix:")
    print(factor_corr)
    print("Factor condition number:", factor_condition_number)

    for name, model in models.items():
        residuals, exposures, summary = _summarize_model(name, model, returns, spec, stocks, factors)
        residuals.to_csv(output_dir / f"residuals_{name}.csv")
        exposures.to_csv(output_dir / f"exposures_{name}.csv")
        summary.to_csv(output_dir / f"summary_{name}.csv", index=False)
        summary_frames.append(summary)
        print(f"\n{name.upper()} exposures:")
        print(exposures)
        print(f"{name.upper()} summary:")
        print(summary)

    comparison = pd.concat(summary_frames, ignore_index=True)
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)
    print("\nCombined comparison:")
    print(comparison)


if __name__ == "__main__":
    main()
