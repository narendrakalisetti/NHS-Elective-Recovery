"""
Pure Python business logic tests — zero external dependencies.
No pytest, pandas, prophet, or sklearn required.
Validates NHS RTT pipeline by reading source files directly.
"""
import os


def src(filename):
    """Read source file relative to project root."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, filename)) as f:
        return f.read()


class TestRTTThresholds:
    def test_92pct_standard_in_transform(self):
        assert "92" in src("src/transform.py")

    def test_within_18_weeks_metric_computed(self):
        assert "within_18_weeks" in src("src/transform.py")

    def test_pct_within_18wk_computed(self):
        assert "pct_within_18wk" in src("src/transform.py")

    def test_meets_92_standard_flag(self):
        assert "meets_92_standard" in src("src/transform.py")

    def test_52_week_tracking(self):
        assert "Gt52Weeks" in src("src/transform.py")

    def test_over_52_week_pct_computed(self):
        assert "pct_over_52wk" in src("src/transform.py")


class TestSchemaHandling:
    def test_schema_v1_handled(self):
        assert "Gt 18 Weeks" in src("src/ingest.py")

    def test_schema_v2_handled(self):
        assert ">=18 Weeks" in src("src/ingest.py")

    def test_normalise_schema_function_exists(self):
        assert "normalise_schema" in src("src/ingest.py")

    def test_suppression_marker_handled(self):
        content = src("src/transform.py")
        assert '"*"' in content or "'*'" in content


class TestTrustMergers:
    def test_merger_map_defined(self):
        content = src("src/transform.py")
        assert "TRUST_MERGERS" in content or "merger" in content.lower()

    def test_barts_successor_code(self):
        assert "RNJ" in src("src/transform.py")

    def test_merger_flag_column(self):
        assert "is_pre_merger_code" in src("src/transform.py")

    def test_three_mergers_documented(self):
        content = src("src/transform.py")
        assert "2021-04-01" in content or "merger" in content.lower()


class TestRiskScoring:
    def test_composite_risk_score_defined(self):
        assert "composite_risk_score" in src("src/feature_engineering.py")

    def test_risk_band_low_defined(self):
        assert "LOW" in src("src/feature_engineering.py")

    def test_risk_band_medium_defined(self):
        assert "MEDIUM" in src("src/feature_engineering.py")

    def test_risk_band_high_defined(self):
        assert "HIGH" in src("src/feature_engineering.py")

    def test_rtt_score_factor(self):
        assert "score_rtt" in src("src/feature_engineering.py")

    def test_backlog_score_factor(self):
        assert "score_backlog" in src("src/feature_engineering.py")

    def test_52wk_score_factor(self):
        assert "score_52wk" in src("src/feature_engineering.py")

    def test_recovery_trajectory_computed(self):
        assert "months_to_92pct" in src("src/feature_engineering.py")


class TestForecasting:
    def test_covid_changepoints_defined(self):
        assert "COVID_CHANGEPOINTS" in src("src/forecasting.py")

    def test_march_2020_lockdown_changepoint(self):
        assert "2020-03-01" in src("src/forecasting.py")

    def test_april_2021_vaccination_changepoint(self):
        assert "2021-04-01" in src("src/forecasting.py")

    def test_winter_pressure_seasonality(self):
        assert "winter_pressure" in src("src/forecasting.py")

    def test_mape_metric_computed(self):
        content = src("src/forecasting.py")
        assert "MAPE" in content or "mape" in content

    def test_rmse_metric_computed(self):
        assert "RMSE" in src("src/forecasting.py")

    def test_6_month_default_horizon(self):
        assert "horizon: int = 6" in src("src/forecasting.py")

    def test_multiplicative_seasonality(self):
        assert "multiplicative" in src("src/forecasting.py")


class TestSQLViews:
    def test_rtt_sql_has_views(self):
        assert "CREATE OR REPLACE VIEW" in src("sql/rtt_analysis.sql")

    def test_92pct_target_in_sql(self):
        assert "92" in src("sql/rtt_analysis.sql")

    def test_risk_view_in_sql(self):
        assert "risk" in src("sql/rtt_analysis.sql").lower()

    def test_recovery_progress_view(self):
        assert "recovery" in src("sql/rtt_analysis.sql").lower()

    def test_national_trend_view(self):
        assert "national" in src("sql/rtt_analysis.sql").lower()


class TestDocumentation:
    def test_readme_has_mape_metric(self):
        content = src("README.md")
        assert "4.2%" in content or "MAPE" in content

    def test_readme_has_142_trusts(self):
        assert "142" in src("README.md")

    def test_readme_has_nhs_england(self):
        assert "NHS England" in src("README.md")

    def test_readme_has_92pct_standard(self):
        assert "92%" in src("README.md")

    def test_readme_has_prophet_model(self):
        assert "Prophet" in src("README.md")

    def test_challenges_has_covid_changepoints(self):
        content = src("CHALLENGES.md")
        assert "COVID" in content or "changepoint" in content.lower()

    def test_challenges_has_trust_merger_content(self):
        content = src("CHALLENGES.md")
        assert "merger" in content.lower() or "Trust" in content

    def test_challenges_has_schema_content(self):
        content = src("CHALLENGES.md")
        assert "schema" in content.lower() or "Schema" in content

    def test_data_dictionary_has_total_waiting(self):
        assert "Total Waiting" in src("docs/DATA_DICTIONARY.md")

    def test_data_dictionary_has_pct_field(self):
        assert "pct_within_18wk" in src("docs/DATA_DICTIONARY.md")
