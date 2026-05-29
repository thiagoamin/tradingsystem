from __future__ import annotations

"""Build daily rolling ETF residuals from split-adjusted ThetaData EOD closes."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.tools.processing import DailyEodPanels
from research.tools.transformer.residualization import (
    FactorSpec,
    RollingFactorResidualizationModel,
    RollingOLSExposureEstimator,
)

from .ingest_theta_eod_data import END_DATE, START_DATE, TECH_STOCKS, run as ingest_eod

ANALYSIS_START_DATE = date(2020, 4, 1)
ESTIMATION_WINDOW = 60
FACTOR_SPECS = {
    "primary_xlk": ["XLK"],
    "robustness_spy_xlk_qqq": ["SPY", "XLK", "QQQ"],
}
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "rolling_etf_residualization"
)


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    analysis_start_date: date = ANALYSIS_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Fetch daily input data and save rolling residualization artifacts."""
    panels = ingest_eod(start_date=start_date, end_date=end_date)
    return build_outputs(panels, analysis_start_date=analysis_start_date, output_root=output_root)


def build_outputs(
    panels: DailyEodPanels,
    analysis_start_date: date = ANALYSIS_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Build no-lookahead residual/exposure paths from daily return panels.

    This separate function permits testing on synthetic panels without making
    ThetaData requests.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []

    for label, (residuals, exposures) in build_residual_paths(panels).items():
        factors = FACTOR_SPECS[label]
        saved_residuals = residuals.loc[pd.Timestamp(analysis_start_date) :]
        saved_exposures = exposures.loc[pd.Timestamp(analysis_start_date) :]
        specification_root = output_root / label
        specification_root.mkdir(parents=True, exist_ok=True)
        saved_residuals.to_csv(specification_root / "rolling_residual_returns.csv")
        saved_exposures.to_csv(specification_root / "rolling_exposures.csv")
        summary_rows.append(
            {
                "specification": label,
                "factors": ",".join(factors),
                "window_days": ESTIMATION_WINDOW,
                "output_rows": len(saved_residuals),
                "complete_residual_rows": int(saved_residuals.notna().all(axis=1).sum()),
                "split_adjusted": panels.split_adjusted,
                "dividend_adjusted": panels.dividend_adjusted,
                "corporate_action_adjusted": panels.corporate_action_adjusted,
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_root / "residualization_summary.csv", index=False)
    return summary


def build_residual_paths(panels: DailyEodPanels) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """Return full rolling residual and exposure paths for each factor specification."""
    returns = panels.returns.sort_index()
    outputs: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for label, factors in FACTOR_SPECS.items():
        model = RollingFactorResidualizationModel(
            spec=FactorSpec({stock: factors for stock in TECH_STOCKS}),
            estimator=RollingOLSExposureEstimator(
                window=ESTIMATION_WINDOW, min_obs=ESTIMATION_WINDOW, fit_intercept=True
            ),
        )
        outputs[label] = (model.fit_transform(returns), _combine_exposure_paths(model))
    return outputs


def _combine_exposure_paths(model: RollingFactorResidualizationModel) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for stock, exposure_path in model.exposure_paths.items():
        renamed = exposure_path.add_prefix(f"{stock}_")
        frames.append(renamed)
    return pd.concat(frames, axis=1)


if __name__ == "__main__":
    result_summary = run()
    print(result_summary.to_string(index=False))
    print(f"Saved split-adjusted rolling residual artifacts to {OUTPUT_ROOT}")
