"""
=============================================================================
NHS Elective Recovery — Feature Engineering & Risk Scoring
=============================================================================
Computes Trust-level risk scores, backlog growth rates, and recovery metrics.
=============================================================================
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path

log = logging.getLogger("NHS.FeatureEngineering")
PROCESSED_DIR = Path("data/processed")


def compute_backlog_growth(df: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month backlog growth per Trust and specialty."""
    df = df.sort_values(["Provider Org Code", "Treatment Function Code", "period_date"])
    df["backlog_mom_pct"] = df.groupby(
        ["Provider Org Code", "Treatment Function Code"]
    )["Total Waiting"].pct_change() * 100
    return df


def compute_trust_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Composite risk score 0-100 per Trust:
      - RTT performance gap vs 92% target (40%)
      - Backlog size percentile rank (30%)
      - 52-week waiter volume (20%)
      - Backlog growth trend (10%)
    """
    latest = (
        df.sort_values("period_date")
        .groupby("Provider Org Code")
        .last()
        .reset_index()
    )

    latest["score_rtt"]     = ((92.0 - latest["pct_within_18wk"]).clip(0) / 92.0 * 40).clip(0, 40)
    latest["score_backlog"] = (latest["Total Waiting"].rank(pct=True) * 30).round(2)
    latest["score_52wk"]    = (latest["Gt52Weeks"].rank(pct=True) * 20).round(2)
    latest["score_growth"]  = (latest["backlog_mom_pct"].clip(0).rank(pct=True) * 10).round(2)

    latest["composite_risk_score"] = (
        latest["score_rtt"] + latest["score_backlog"] +
        latest["score_52wk"] + latest["score_growth"]
    ).round(2).clip(0, 100)

    latest["risk_band"] = pd.cut(
        latest["composite_risk_score"],
        bins=[0, 40, 70, 100],
        labels=["LOW", "MEDIUM", "HIGH"],
        include_lowest=True
    )
    return latest


def compute_recovery_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate months for each Trust to reach 92% RTT standard."""
    trends = (
        df.groupby(["Provider Org Code", "period_date"])["pct_within_18wk"]
        .mean().reset_index()
        .sort_values(["Provider Org Code", "period_date"])
    )
    trends["improvement_rate"] = trends.groupby("Provider Org Code")["pct_within_18wk"] \
        .transform(lambda x: x.diff().rolling(3).mean())

    latest = trends.groupby("Provider Org Code").last().reset_index()
    latest["gap_to_target"] = (92.0 - latest["pct_within_18wk"]).clip(0)
    latest["months_to_92pct"] = np.where(
        latest["improvement_rate"] > 0,
        (latest["gap_to_target"] / latest["improvement_rate"]).round(0),
        999
    )
    latest["on_track_by_mar_2025"] = latest["months_to_92pct"] <= 14
    return latest


def run_feature_pipeline(save: bool = True) -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "rtt_processed.parquet")
    df = compute_backlog_growth(df)
    scores = compute_trust_risk_scores(df)
    trajectory = compute_recovery_trajectory(df)
    result = scores.merge(
        trajectory[["Provider Org Code", "months_to_92pct", "on_track_by_mar_2025"]],
        on="Provider Org Code", how="left"
    )
    if save:
        result.to_parquet(PROCESSED_DIR / "trust_risk_scores.parquet", index=False)
    log.info("Feature engineering complete: %d Trusts scored", len(result))
    return result


if __name__ == "__main__":
    run_feature_pipeline()
