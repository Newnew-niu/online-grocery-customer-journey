"""Step 20: Run the GA4 session-funnel SQL in BigQuery and save the result.

You need:
1. A Google Cloud project (the free BigQuery sandbox is enough).
2. To log in once: a browser window opens; the login is saved in your
   user folder, not in this repo.

Usage:
    python src/20_run_ga4_query.py --project YOUR_PROJECT_ID

The script first does a "dry run" to show how many bytes the query will scan,
then runs it and saves data/raw/ga4/ga4_sessions.parquet.
"""
import argparse
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from bq_auth import get_credentials

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "01_session_funnel.sql"
OUT = ROOT / "data" / "raw" / "ga4" / "ga4_sessions.parquet"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="Your Google Cloud project ID (used for billing / sandbox).")
    args = ap.parse_args()

    creds = get_credentials()
    project = args.project
    if not project:
        projects = list(bigquery.Client(credentials=creds, project="bigquery-public-data").list_projects())
        if len(projects) != 1:
            raise SystemExit(f"Please pass --project. Your projects: {[p.project_id for p in projects]}")
        project = projects[0].project_id
    client = bigquery.Client(credentials=creds, project=project)
    sql = SQL.read_text(encoding="utf-8")

    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    print(f"Project: {project}. This query will scan {dry.total_bytes_processed / 1e9:.2f} GB.")

    df = client.query(sql).to_dataframe()
    df["session_date"] = pd.to_datetime(df["session_date"].astype(str))  # BigQuery date -> normal date
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Saved {len(df):,} sessions to {OUT}")


if __name__ == "__main__":
    main()
