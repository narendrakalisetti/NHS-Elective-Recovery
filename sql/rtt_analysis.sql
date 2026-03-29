-- =============================================================================
-- NHS Elective Recovery — RTT Analysis SQL
-- =============================================================================
-- Engine: DuckDB / PostgreSQL / Azure Synapse Serverless
-- Author: Narendra Kalisetti
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. National RTT Performance — Monthly Trend
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_national_rtt_trend AS
SELECT
    period_date,
    period_year,
    period_month,
    SUM("Total Waiting")                                    AS total_waiting,
    SUM(within_18_weeks)                                    AS within_18_weeks,
    SUM("Gt18Weeks")                                        AS over_18_weeks,
    SUM("Gt52Weeks")                                        AS over_52_weeks,
    ROUND(SUM(within_18_weeks) * 100.0 /
          NULLIF(SUM("Total Waiting"), 0), 2)               AS pct_within_18wk,
    92.0                                                    AS target_pct,
    ROUND(92.0 - SUM(within_18_weeks) * 100.0 /
          NULLIF(SUM("Total Waiting"), 0), 2)               AS gap_to_target_pct,
    -- Rolling 3-month average
    AVG(ROUND(SUM(within_18_weeks) * 100.0 /
              NULLIF(SUM("Total Waiting"), 0), 2))
        OVER (ORDER BY period_date
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)    AS rolling_3m_pct
FROM rtt_processed
GROUP BY period_date, period_year, period_month
ORDER BY period_date DESC;

-- ---------------------------------------------------------------------------
-- 2. Trust-Level RTT Performance (Latest Period)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_trust_rtt_latest AS
SELECT
    r."Provider Org Code"                                   AS trust_code,
    r."Provider Org Name"                                   AS trust_name,
    r.period_date,
    SUM(r."Total Waiting")                                  AS total_waiting,
    SUM(r.within_18_weeks)                                  AS within_18_weeks,
    SUM(r."Gt52Weeks")                                      AS over_52_weeks,
    ROUND(SUM(r.within_18_weeks) * 100.0 /
          NULLIF(SUM(r."Total Waiting"), 0), 2)             AS pct_within_18wk,
    CASE
        WHEN ROUND(SUM(r.within_18_weeks) * 100.0 /
                   NULLIF(SUM(r."Total Waiting"), 0), 2) >= 92 THEN 'MEETS TARGET'
        WHEN ROUND(SUM(r.within_18_weeks) * 100.0 /
                   NULLIF(SUM(r."Total Waiting"), 0), 2) >= 75 THEN 'CLOSE TO TARGET'
        ELSE 'BELOW TARGET'
    END                                                     AS performance_status,
    s.composite_risk_score,
    s.risk_band
FROM rtt_processed r
LEFT JOIN trust_risk_scores s ON r."Provider Org Code" = s."Provider Org Code"
WHERE r.period_date = (SELECT MAX(period_date) FROM rtt_processed)
GROUP BY r."Provider Org Code", r."Provider Org Name", r.period_date,
         s.composite_risk_score, s.risk_band
ORDER BY pct_within_18wk ASC;

-- ---------------------------------------------------------------------------
-- 3. Specialty Breakdown — Worst Performing Pathways
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_specialty_rtt AS
SELECT
    "Treatment Function Name"                               AS specialty,
    period_date,
    SUM("Total Waiting")                                    AS total_waiting,
    SUM("Gt18Weeks")                                        AS over_18_weeks,
    ROUND(SUM("Gt18Weeks") * 100.0 /
          NULLIF(SUM("Total Waiting"), 0), 2)               AS pct_over_18wk,
    ROUND(SUM("Gt52Weeks") * 100.0 /
          NULLIF(SUM("Total Waiting"), 0), 2)               AS pct_over_52wk,
    -- Rank worst performing specialties
    RANK() OVER (
        PARTITION BY period_date
        ORDER BY SUM("Gt18Weeks") * 100.0 / NULLIF(SUM("Total Waiting"),0) DESC
    )                                                       AS worst_rank
FROM rtt_processed
WHERE period_date = (SELECT MAX(period_date) FROM rtt_processed)
GROUP BY "Treatment Function Name", period_date
ORDER BY pct_over_18wk DESC;

-- ---------------------------------------------------------------------------
-- 4. High-Risk Trusts — Intervention Priority List
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_high_risk_trusts AS
SELECT
    trust_code,
    trust_name,
    total_waiting,
    pct_within_18wk,
    ROUND(92.0 - pct_within_18wk, 2)                       AS gap_to_target_pct,
    over_52_weeks,
    composite_risk_score,
    risk_band,
    -- Waiting list size context
    CASE
        WHEN total_waiting >= 50000 THEN 'LARGE (50k+)'
        WHEN total_waiting >= 20000 THEN 'MEDIUM (20-50k)'
        ELSE 'SMALL (<20k)'
    END                                                     AS trust_size_band
FROM v_trust_rtt_latest
WHERE risk_band = 'HIGH'
ORDER BY composite_risk_score DESC;

-- ---------------------------------------------------------------------------
-- 5. Recovery Progress — Month-over-Month Change
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_recovery_progress AS
SELECT
    period_date,
    total_waiting,
    pct_within_18wk,
    LAG(total_waiting)     OVER (ORDER BY period_date)      AS prev_month_waiting,
    LAG(pct_within_18wk)   OVER (ORDER BY period_date)      AS prev_month_pct,
    total_waiting - LAG(total_waiting) OVER
        (ORDER BY period_date)                              AS waiting_mom_change,
    ROUND(pct_within_18wk - LAG(pct_within_18wk) OVER
        (ORDER BY period_date), 2)                          AS rtt_pct_mom_change,
    -- Year-over-year comparison
    LAG(pct_within_18wk, 12) OVER (ORDER BY period_date)   AS same_month_last_year_pct,
    ROUND(pct_within_18wk - LAG(pct_within_18wk, 12) OVER
        (ORDER BY period_date), 2)                          AS rtt_pct_yoy_change
FROM v_national_rtt_trend
ORDER BY period_date DESC;
