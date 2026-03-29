# Data Dictionary — NHS RTT Analytics

## Source: NHS England RTT Waiting Times Open Data
**Licence:** Open Government Licence v3.0
**URL:** https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/

## Key Fields

| Field | Description | Type |
|---|---|---|
| Period | Reporting month (e.g. "January 2024") | String |
| Provider Org Code | NHS Trust ODS code (e.g. "RJ1") | String |
| Provider Org Name | NHS Trust full name | String |
| Treatment Function Code | Clinical specialty code | String |
| Treatment Function Name | Clinical specialty name | String |
| Total Waiting | Total number of incomplete pathways | Integer |
| Gt18Weeks | Pathways waiting >18 weeks | Integer |
| Gt52Weeks | Pathways waiting >52 weeks | Integer |

## Derived Fields

| Field | Formula | Description |
|---|---|---|
| within_18_weeks | Total Waiting - Gt18Weeks | Pathways within target |
| pct_within_18wk | within_18_weeks / Total Waiting * 100 | RTT performance % |
| meets_92_standard | pct_within_18wk >= 92.0 | NHS constitutional standard |
| composite_risk_score | Weighted 0-100 score | Trust intervention priority |

## Data Quality Notes
- Counts <5 suppressed with '*' — treated as 0 in aggregations
- Schema changed 3 times 2019–2024 — handled by normalise_schema()
- Three Trust mergers 2021–2022 — flagged in is_pre_merger_code field
