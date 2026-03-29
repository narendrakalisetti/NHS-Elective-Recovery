"""
Unit tests for NHS Elective Recovery pipeline.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.transform import (
    parse_period, clean_numeric_columns, calculate_rtt_metrics, flag_trust_mergers
)
from src.feature_engineering import compute_backlog_growth, compute_trust_risk_scores


@pytest.fixture
def sample_rtt_df():
    return pd.DataFrame({
        "Period":               ["April 2023", "May 2023", "April 2023", "May 2023"],
        "Provider Org Code":    ["RJ1", "RJ1", "RNJ", "RNJ"],
        "Provider Org Name":    ["Trust A", "Trust A", "Trust B", "Trust B"],
        "Treatment Function Code": ["100", "100", "110", "110"],
        "Treatment Function Name": ["General Surgery", "General Surgery", "Orthopaedics", "Orthopaedics"],
        "RTT Part Description": ["Admitted", "Admitted", "Admitted", "Admitted"],
        "Total Waiting":        ["1000", "1050", "500", "*"],
        "Gt18Weeks":            ["200", "180", "150", "*"],
        "Gt52Weeks":            ["10", "8", "20", "*"],
        "source_file":          ["RTT_2023_04.csv"] * 4,
    })


class TestParseperiod:
    def test_parses_month_year_format(self, sample_rtt_df):
        result = parse_period(sample_rtt_df)
        assert "period_date" in result.columns
        assert result["period_date"].dtype == "datetime64[ns]"

    def test_extracts_year_and_month(self, sample_rtt_df):
        result = parse_period(sample_rtt_df)
        assert result["period_year"].iloc[0] == 2023
        assert result["period_month"].iloc[0] == 4


class TestCleanNumeric:
    def test_converts_strings_to_int(self, sample_rtt_df):
        result = clean_numeric_columns(sample_rtt_df)
        assert result["Total Waiting"].dtype in [int, "int64"]

    def test_handles_suppression_marker(self, sample_rtt_df):
        """NHS suppresses counts < 5 with '*' — treated as 0."""
        result = clean_numeric_columns(sample_rtt_df)
        # Row with '*' should become 0
        assert result[result["Provider Org Code"] == "RNJ"]["Total Waiting"].iloc[1] == 0

    def test_no_negative_values(self, sample_rtt_df):
        result = clean_numeric_columns(sample_rtt_df)
        assert (result["Total Waiting"] >= 0).all()
        assert (result["Gt18Weeks"] >= 0).all()


class TestRTTMetrics:
    def test_pct_within_18wk_calculation(self, sample_rtt_df):
        df = clean_numeric_columns(sample_rtt_df)
        df = calculate_rtt_metrics(df)
        # Trust A, April: (1000-200)/1000 * 100 = 80%
        row = df[(df["Provider Org Code"] == "RJ1") & (df["Period"] == "April 2023")].iloc[0]
        assert row["pct_within_18wk"] == pytest.approx(80.0, abs=0.01)

    def test_meets_92_standard_flag(self, sample_rtt_df):
        df = clean_numeric_columns(sample_rtt_df)
        df = calculate_rtt_metrics(df)
        # 80% does not meet 92% standard
        assert not df[df["Provider Org Code"] == "RJ1"]["meets_92_standard"].all()

    def test_no_pct_for_zero_waiting(self):
        df = pd.DataFrame({
            "Total Waiting": [0, 100],
            "Gt18Weeks":     [0, 20],
            "Gt52Weeks":     [0, 5],
        })
        result = calculate_rtt_metrics(df)
        assert pd.isna(result["pct_within_18wk"].iloc[0])
        assert result["pct_within_18wk"].iloc[1] == pytest.approx(80.0)


class TestTrustMergers:
    def test_flags_pre_merger_codes(self, sample_rtt_df):
        df = clean_numeric_columns(sample_rtt_df)
        # RNJ is a merged Trust code
        df_merged = flag_trust_mergers(df)
        assert "is_pre_merger_code" in df_merged.columns

    def test_non_merger_trust_not_flagged(self, sample_rtt_df):
        df = clean_numeric_columns(sample_rtt_df)
        df = flag_trust_mergers(df)
        rj1_rows = df[df["Provider Org Code"] == "RJ1"]
        assert not rj1_rows["is_pre_merger_code"].any()


class TestRiskScoring:
    def test_risk_score_range(self, sample_rtt_df):
        df = parse_period(sample_rtt_df)
        df = clean_numeric_columns(df)
        df = calculate_rtt_metrics(df)
        df = compute_backlog_growth(df)
        scores = compute_trust_risk_scores(df)
        assert scores["composite_risk_score"].between(0, 100).all()

    def test_risk_bands_assigned(self, sample_rtt_df):
        df = parse_period(sample_rtt_df)
        df = clean_numeric_columns(df)
        df = calculate_rtt_metrics(df)
        df = compute_backlog_growth(df)
        scores = compute_trust_risk_scores(df)
        assert scores["risk_band"].isin(["LOW", "MEDIUM", "HIGH"]).all()

    def test_low_rtt_performance_increases_risk(self):
        """Trust with 40% RTT should score higher than Trust with 85% RTT."""
        rows = []
        for trust, pct_within in [("T_LOW", 40.0), ("T_HIGH", 85.0)]:
            for month in ["2023-01-01", "2023-02-01", "2023-03-01"]:
                total = 10000
                gt18 = int(total * (1 - pct_within / 100))
                rows.append({
                    "Provider Org Code": trust,
                    "Treatment Function Code": "100",
                    "period_date": pd.Timestamp(month),
                    "Total Waiting": total,
                    "Gt18Weeks": gt18,
                    "Gt52Weeks": max(0, gt18 // 5),
                    "within_18_weeks": total - gt18,
                    "pct_within_18wk": pct_within,
                    "meets_92_standard": pct_within >= 92,
                    "pct_over_52wk": max(0, gt18 // 5) / total * 100,
                    "backlog_mom_pct": 1.0,
                })
        df = pd.DataFrame(rows)
        scores = compute_trust_risk_scores(df).set_index("Provider Org Code")
        assert scores.loc["T_LOW", "composite_risk_score"] > scores.loc["T_HIGH", "composite_risk_score"]
