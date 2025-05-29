Below is a Python script that:
	1.	Fetches the list of Reporting Issuers from SEDAR+
	2.	Fetches filing metadata for a given date range via the CSV export endpoint
	3.	Downloads each document’s URL (PDF)
	4.	Inserts issuer and filing metadata into a Supabase PostgreSQL database

You’ll need to set these environment variables:

export SEDAR_BASE_URL="https://www.sedarplus.ca"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-or-service-role-key"
export SUPABASE_SCHEMA="public"           # optional, defaults to public

Install dependencies:

pip install requests pandas supabase

#!/usr/bin/env python3
import os
import time
import uuid
import logging
from typing import List, Dict
import requests
import pandas as pd
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment config
SEDAR_BASE = os.getenv("SEDAR_BASE_URL", "https://www.sedarplus.ca")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SCHEMA = os.getenv("SUPABASE_SCHEMA", "public")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_issuers_csv() -> pd.DataFrame:
    """
    Fetch the full Reporting Issuers list CSV from SEDAR+.
    """
    url = f"{SEDAR_BASE}/csa-party/service/exportCsv"
    # This payload mirrors what the "Export" button on the Issuers page uses.
    payload = {
        "service": "reportingIssuers",
        "queryArgs": {
            "_locale": "en",
            "start": 1,
            "pageSize": 10000
        }
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    # The response body is the CSV text
    df = pd.read_csv(pd.compat.StringIO(resp.text))
    logger.info(f"Fetched {len(df)} issuers")
    return df

def insert_issuers(df: pd.DataFrame):
    """
    Insert or upsert issuer rows into Supabase table 'dim_issuer'.
    """
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "issuer_no": row["Issuer Number"],
            "name": row["Name"],
            "jurisdiction": row["Jurisdiction(s)"],
            "issuer_type": row["Type"],
            "in_default": row["In Default Flag"].astype(bool),
            "active_cto": row["Active CTO Flag"].astype(bool),
        })
    # Use upsert to avoid duplicates
    res = supabase.table("dim_issuer").upsert(rows, on_conflict="issuer_no").execute()
    if res.error:
        logger.error("Error upserting issuers: %s", res.error)
    else:
        logger.info(f"Upserted {len(rows)} issuers")

def fetch_filings_for_date(date_str: str) -> pd.DataFrame:
    """
    Fetch all filings submitted on a given date (YYYY-MM-DD).
    """
    url = f"{SEDAR_BASE}/csa-party/service/exportCsv"
    payload = {
        "service": "searchDocuments",
        "queryArgs": {
            "_locale": "en",
            "fromDate": date_str,
            "toDate": date_str,
            "start": 1,
            "pageSize": 5000  # adjust if needed
        }
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    df = pd.read_csv(pd.compat.StringIO(resp.text))
    logger.info(f"Fetched {len(df)} filings for {date_str}")
    return df

def insert_filings(df: pd.DataFrame):
    """
    Insert or upsert filing metadata into Supabase table 'fact_filing'.
    Assumes table fact_filing has columns matching the keys below.
    """
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "filing_id": str(uuid.uuid4()),
            "issuer_no": row["Issuer Number"],
            "document_guid": row["Document GUID"],
            "filing_type": row["Filing Type"],
            "document_type": row["Document Type"],
            "submitted_date": row["Date Filed"],
            "url": row["Generate URL"],
            "size_bytes": row.get("Size", None),
            "version": row.get("Version", 1),
        })
    res = supabase.table("fact_filing").upsert(rows, on_conflict="document_guid").execute()
    if res.error:
        logger.error("Error upserting filings: %s", res.error)
    else:
        logger.info(f"Upserted {len(rows)} filings")

def download_and_store_pdfs(df: pd.DataFrame, download_dir: str = "./pdfs"):
    """
    Download PDFs from the 'Generate URL' field and save locally.
    """
    os.makedirs(download_dir, exist_ok=True)
    for idx, row in df.iterrows():
        url = row["Generate URL"]
        guid = row["Document GUID"]
        local_path = os.path.join(download_dir, f"{guid}.pdf")
        if os.path.exists(local_path):
            continue  # already downloaded
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(r.content)
            time.sleep(0.2)  # polite delay
            logger.info(f"Downloaded {guid}.pdf")
        except Exception as e:
            logger.warning(f"Failed to download {guid}: {e}")

def main():
    # 1) Ingest issuers
    issuers_df = fetch_issuers_csv()
    insert_issuers(issuers_df)

    # 2) Ingest filings for the last 7 days (example)
    from datetime import datetime, timedelta
    for d in range(7):
        date = (datetime.utcnow() - timedelta(days=d)).strftime("%Y-%m-%d")
        filings_df = fetch_filings_for_date(date)
        insert_filings(filings_df)
        download_and_store_pdfs(filings_df)

if __name__ == "__main__":
    main()

Notes & Next Steps:
	•	You’ll need to create the tables in your Supabase PostgreSQL project matching the dim_issuer and fact_filing schemas. For example:

-- Issuers dimension
CREATE TABLE IF NOT EXISTS public.dim_issuer (
  issuer_no text PRIMARY KEY,
  name text,
  jurisdiction text,
  issuer_type text,
  in_default boolean,
  active_cto boolean
);

-- Filings fact
CREATE TABLE IF NOT EXISTS public.fact_filing (
  filing_id uuid PRIMARY KEY,
  issuer_no text REFERENCES public.dim_issuer(issuer_no),
  document_guid text UNIQUE,
  filing_type text,
  document_type text,
  submitted_date date,
  url text,
  size_bytes bigint,
  version integer
);


	•	Adjust pageSize if you expect more than 5,000 filings on a single day.
	•	Extend the script to parse PDFs (e.g., with pdfminer.six or PyPDF2) and insert structured financial data as shown in the earlier schema.
	•	Add error handling, retries, and logging for production readiness.
	•	Schedule this script via cron, Airflow, or another scheduler to run daily (or more frequently) to keep your Supabase database up to date.