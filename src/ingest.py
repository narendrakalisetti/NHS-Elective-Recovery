"""
=============================================================================
NHS Elective Recovery — Data Ingestion
=============================================================================
Downloads NHS England RTT Waiting Times open data CSV files.
Data source: NHS England Statistics — RTT Waiting Times (Open Government Licence v3.0)
No PII — all data is Trust-level aggregated counts.
=============================================================================
"""

import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("NHS.Ingest")

RAW_DATA_DIR = Path("data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_COLUMNS_V3 = [
    "Period", "Provider Org Code", "Provider Org Name",
    "Treatment Function Code", "Treatment Function Name",
    "RTT Part Description", "Total Waiting", "Gt18Weeks", "Gt52Weeks",
]


def download_rtt_month(year: int, month: int, force: bool = False) -> Optional[Path]:
    """Download a single month of NHS England RTT data."""
    month_name = datetime(year, month, 1).strftime("%B")
    filename = f"RTT_{year}_{month:02d}.csv"
    filepath = RAW_DATA_DIR / filename

    if filepath.exists() and not force:
        log.info("Already downloaded: %s", filename)
        return filepath

    # NHS England RTT open data URL pattern
    url = (
        f"https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/"
        f"{year}/{month:02d}/RTT-{month_name}-{year}.csv"
    )
    log.info("Downloading: %s", url)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        filepath.write_bytes(response.content)
        log.info("Saved: %s (%.1f KB)", filename, len(response.content) / 1024)
        return filepath
    except requests.HTTPError as e:
        log.warning("HTTP error for %s: %s", filename, e)
        return None
    except requests.RequestException as e:
        log.error("Failed to download %s: %s", filename, e)
        return None


def download_last_n_months(n: int = 12, force: bool = False) -> list:
    """Download the last n months of RTT data. NHS publishes with ~2 month lag."""
    downloaded = []
    today = datetime.today()
    for i in range(n):
        target = today - timedelta(days=30 * (i + 2))
        path = download_rtt_month(target.year, target.month, force=force)
        if path:
            downloaded.append(path)
    log.info("Downloaded %d/%d months successfully", len(downloaded), n)
    return downloaded


def normalise_schema(df: pd.DataFrame, filepath: Path) -> pd.DataFrame:
    """
    NHS England changed RTT CSV column names 3 times between 2019-2024.
    Normalise all historical versions to a consistent schema.
    """
    cols = df.columns.tolist()

    # Schema V1 (pre-2020)
    if "Gt 18 Weeks" in cols:
        log.info("%s: Schema V1 — normalising", filepath.name)
        df = df.rename(columns={"Gt 18 Weeks": "Gt18Weeks", "Gt 52 Weeks": "Gt52Weeks"})

    # Schema V2 (2020-2022)
    elif ">=18 Weeks" in cols:
        log.info("%s: Schema V2 — normalising", filepath.name)
        df = df.rename(columns={">=18 Weeks": "Gt18Weeks", ">=52 Weeks": "Gt52Weeks"})

    return df


def load_rtt_file(filepath: Path) -> Optional[pd.DataFrame]:
    """Load a single RTT CSV, normalise schema, return DataFrame."""
    try:
        df = pd.read_csv(filepath, encoding="utf-8-sig", low_memory=False)
        df.columns = df.columns.str.strip()
        df = normalise_schema(df, filepath)
        df["source_file"] = filepath.name
        return df
    except Exception as e:
        log.error("Failed to load %s: %s", filepath, e)
        return None


def load_all_raw(data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load and concatenate all downloaded RTT CSV files."""
    files = sorted(data_dir.glob("RTT_*.csv"))
    if not files:
        raise FileNotFoundError(f"No RTT CSV files found in {data_dir}. Run ingest first.")

    dfs = [load_rtt_file(f) for f in files]
    dfs = [df for df in dfs if df is not None]
    combined = pd.concat(dfs, ignore_index=True)
    log.info("Loaded %d records from %d files", len(combined), len(dfs))
    return combined


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    download_last_n_months(n=args.months, force=args.force)
