from __future__ import annotations

"""Estimate daily OU parameters and s-scores from split-adjusted residuals."""

from datetime import date
from pathlib import Path

import pandas as pd

from research.tools.processing import DailyEodPanels
from research.tools.transformer.mean_reversion import OUEstimator, RollingOUScoreModel

from .ingest_theta_eod_data import END_DATE, START_DATE, run as ingest_eod
from .rolling_etf_residualization import ESTIMATION_WINDOW, build_residual_paths

SCORE_START_DATE = date(2020, 7, 1)
MAX_MEAN_REVERSION_DAYS = 30.0
OUTPUT_ROOT = (
    Path("research")
    / "experiment_outputs"
    / "avellaneda_lee_2008"
    / "one_day"
    / "ou_scores"
)


def run(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    score_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Fetch ThetaData EOD input data and save OU/s-score artifacts."""
    panels = ingest_eod(start_date=start_date, end_date=end_date)
    return build_outputs(panels, score_start_date=score_start_date, output_root=output_root)


def build_outputs(
    panels: DailyEodPanels,
    score_start_date: date = SCORE_START_DATE,
    output_root: Path = OUTPUT_ROOT,
) -> pd.DataFrame:
    """Compute and persist lagged daily OU/s-score paths."""
    model = RollingOUScoreModel(
        window=ESTIMATION_WINDOW,
        estimator=OUEstimator(max_mean_reversion_days=MAX_MEAN_REVERSION_DAYS),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    start_timestamp = pd.Timestamp(score_start_date)
    summary_rows: list[dict[str, object]] = []

    for label, (residuals, _) in build_residual_paths(panels).items():
        result = model.transform(residuals)
        scores = result.scores.loc[start_timestamp:]
        eligibility = result.eligibility.loc[start_timestamp:]
        parameters = _after_date(result.parameters, start_timestamp)

        specification_root = output_root / label
        specification_root.mkdir(parents=True, exist_ok=True)
        scores.to_csv(specification_root / "s_scores.csv")
        eligibility.to_csv(specification_root / "eligibility.csv")
        parameters.to_csv(specification_root / "ou_parameters.csv")
        summary_rows.append(
            {
                "specification": label,
                "window_days": ESTIMATION_WINDOW,
                "max_mean_reversion_days": MAX_MEAN_REVERSION_DAYS,
                "score_rows": len(scores),
                "stock_score_observations": int(scores.notna().sum().sum()),
                "eligible_stock_days": int(eligibility.sum().sum()),
                "split_adjusted": panels.split_adjusted,
                "dividend_adjusted": panels.dividend_adjusted,
                "corporate_action_adjusted": panels.corporate_action_adjusted,
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_root / "ou_score_summary.csv", index=False)
    return summary


def _after_date(parameters: pd.DataFrame, start_timestamp: pd.Timestamp) -> pd.DataFrame:
    if parameters.empty:
        return parameters
    timestamp_values = parameters.index.get_level_values("timestamp")
    return parameters.loc[timestamp_values >= start_timestamp]


if __name__ == "__main__":
    ou_summary = run()
    print(ou_summary.to_string(index=False))
    print(f"Saved split-adjusted OU/s-score artifacts to {OUTPUT_ROOT}")
