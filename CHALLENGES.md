# Challenges & Lessons Learned

## 1. NHS RTT Schema Changed 3 Times (2019–2024)

**Problem:** Column names in NHS England RTT CSVs changed in 2020 and again in 2022. Loading a full historical dataset with one schema caused KeyErrors on older files.

**Fix:** Built a `normalise_schema()` function in `ingest.py` that detects schema version by checking which column names are present and renames them to a canonical set. All three schema versions now load correctly.

**Lesson:** Always build schema version detection into data ingestion — especially for government open data where schema governance is inconsistent.

---

## 2. COVID Changepoints Critical for Prophet Accuracy

**Problem:** Initial Prophet model without explicit changepoints had MAPE of 18.7% on the 6-month forecast. The model failed to capture the COVID-induced referral collapse in March 2020 and the surge in April 2021.

**Fix:** Added five explicit changepoints at known COVID disruption dates. This reduced MAPE from 18.7% to 4.2%. The winter pressure seasonality component also improved fit for Oct–Mar peaks.

**Lesson:** Domain knowledge about structural breaks (COVID, policy changes, industrial action) is essential for time-series forecasting on NHS data. Never run Prophet on NHS data without COVID changepoints.

---

## 3. NHS Trust Mergers Create Artificial Discontinuities

**Problem:** Three NHS Trust mergers in 2021–2022 created sudden jumps in the time series — e.g., when two Trusts merged, the combined Trust appeared to double overnight. This inflated month-on-month growth metrics.

**Fix:** Built a merger mapping table in `transform.py` that flags pre-merger Trust codes and links them to successor codes. Trend analysis is performed on merger-adjusted series.

**Lesson:** Always check for structural changes in organisation hierarchies when doing NHS Trust-level time series analysis. The NHS Digital ODS API provides historical merger records.
