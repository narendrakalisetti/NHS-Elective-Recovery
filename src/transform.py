"""
=============================================================================
NHS Elective Recovery — Data Transformation
=============================================================================
Cleans and standardises raw RTT data into analysis-ready format.
Handles NHS Trust mergers, data suppression markers, and schema versions.
=============================================================================
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path

log = logging.getLogger("NHS.Transform")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# NHS Trust mergers during 2021-2023 — creates discontinuities in time series
TRUST_MERGERS = {
    "RQW": ("RNJ", "2021-04-01"),   # Barts Health
    "RDD": ("RDE", "2021-04-01"),   # Mid and South Essex
    "RAJ": ("RDE", "2021-04-01"),   # Mid and South Essex
    "RP9": ("RQ3", "2022-10-01"),   # Birmingham and Solihull
}


def parse_period(df: pd.DataFrame) -> pd.DataFrame:
    """Parse NHS RTT period strings into datetime."""
    df["period_date"] = pd.to_datetime(df["Period"], format="mixed", dayfirst=True)
    df["period_year"] = df["period_date"].dt.year
    df["period_month"] = df["period_date"].dt.month
    return df


def clean_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert waiting count columns to numeric.
    NHS suppresses counts <5 with '*' — treated as 0 for aggregation
    (conservative approach approved by NHS Digital IG guidance).
    """
    for col in ["Total Waiting", "Gt18Weeks", "Gt52Weeks"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("*", "0", regex=False).str.strip(),
                errors="coerce"
            ).fillna(0).astype(int)
    return df


def calculate_rtt_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RTT performance metrics. NHS standard: 92% within 18 weeks."""
    df["within_18_weeks"] = df["Total Waiting"] - df["Gt18Weeks"]
    df["pct_within_18wk"] = np.where(
        df["Total Waiting"] > 0,
        (df["within_18_weeks"] / df["Total Waiting"] * 100).round(2),
        np.nan
    )
    df["meets_92_standard"] = df["pct_within_18wk"] >= 92.0
    df["pct_over_52wk"] = np.where(
        df["Total Waiting"] > 0,
        (df["Gt52Weeks"] / df["Total Waiting"] * 100).round(2),
        np.nan
    )
    return df


def flag_trust_mergers(df: pd.DataFrame) -> pd.DataFrame:
    """Flag pre-merger Trust codes to prevent double-counting."""
    df["is_pre_merger_code"] = df["Provider Org Code"].isin(TRUST_MERGERS.keys())
    df["successor_org_code"] = df["Provider Org Code"].map(
        {k: v[0] for k, v in TRUST_MERGERS.items()}
    )
    return df


def transform_pipeline(input_df: pd.DataFrame = None, save: bool = True) -> pd.DataFrame:
    """Run the full transformation pipeline."""
    if input_df is None:
        from src.ingest import load_all_raw
        input_df = load_all_raw()

    log.info("Starting transformation: %d raw rows", len(input_df))
    df = parse_period(input_df)
    df = clean_numeric_columns(df)
    df = calculate_rtt_metrics(df)
    df = flag_trust_mergers(df)

    # Filter: remove ICB-level aggregates (Provider codes starting with Q)
    df = df[df["Provider Org Code"].notna()]
    df = df[~df["Provider Org Code"].str.startswith("Q", na=False)]
    # Filter: remove rows with implausible waiting counts
    df = df[df["Total Waiting"] > 0]

    log.info("Transformation complete: %d rows, %d columns", len(df), len(df.columns))

    if save:
        out_path = PROCESSED_DIR / "rtt_processed.parquet"
        df.to_parquet(out_path, index=False)
        log.info("Saved: %s", out_path)

    return df


if __name__ == "__main__":
    transform_pipeline()
