#!/usr/bin/env python3
"""
SEDAR+ Data Collection Script
============================

A comprehensive script to collect Canadian financial data from SEDAR+ following
the architectural principles outlined in the technical blueprint.

Features:
- Rate-limited and respectful data collection
- Robust error handling and retry logic
- Modular design for scalability
- Support for both historical and incremental updates
- Compliance with SEDAR+ terms of use
"""

import os
import time
import uuid
import logging
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import requests
import pandas as pd
from supabase import create_client, Client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sedar_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SedarConfig:
    """Configuration for SEDAR+ data collection"""
    base_url: str = "https://www.sedarplus.ca"
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    schema: str = "public"
    rate_limit_delay: float = 1.0  # seconds between requests
    max_retries: int = 3
    batch_size: int = 5000
    download_dir: str = "./data/pdfs"
    cache_dir: str = "./data/cache"

class SedarCollector:
    """Main class for collecting data from SEDAR+"""
    
    def __init__(self, config: SedarConfig):
        self.config = config
        self.session = self._setup_session()
        self.supabase = self._setup_supabase() if config.supabase_url else None
        self._ensure_directories()
        
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set user agent to be respectful
        session.headers.update({
            'User-Agent': 'SedarAnalytics/1.0 (Educational Research)'
        })
        
        return session
    
    def _setup_supabase(self) -> Optional[Client]:
        """Setup Supabase client if credentials provided"""
        if not self.config.supabase_url or not self.config.supabase_key:
            logger.warning("Supabase credentials not provided. Data will be saved locally only.")
            return None
            
        try:
            return create_client(self.config.supabase_url, self.config.supabase_key)
        except Exception as e:
            logger.error(f"Failed to setup Supabase client: {e}")
            return None
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        Path(self.config.download_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def _rate_limit(self):
        """Apply rate limiting to be respectful to SEDAR+ servers"""
        time.sleep(self.config.rate_limit_delay)
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited request with error handling"""
        self._rate_limit()
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def fetch_issuers_csv(self) -> pd.DataFrame:
        """
        Fetch the complete list of reporting issuers from SEDAR+
        """
        logger.info("Fetching reporting issuers list...")
        
        url = f"{self.config.base_url}/csa-party/service/exportCsv"
        payload = {
            "service": "reportingIssuers",
            "queryArgs": {
                "_locale": "en",
                "start": 1,
                "pageSize": 10000
            }
        }
        
        try:
            response = self._make_request("POST", url, json=payload)
            df = pd.read_csv(pd.io.common.StringIO(response.text))
            logger.info(f"Successfully fetched {len(df)} issuers")
            
            # Cache the result
            cache_file = Path(self.config.cache_dir) / f"issuers_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(cache_file, index=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch issuers: {e}")
            raise
    
    def fetch_filings_for_date_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch all filings for a given date range (YYYY-MM-DD format)
        """
        logger.info(f"Fetching filings from {start_date} to {end_date}")
        
        url = f"{self.config.base_url}/csa-party/service/exportCsv"
        payload = {
            "service": "searchDocuments",
            "queryArgs": {
                "_locale": "en",
                "fromDate": start_date,
                "toDate": end_date,
                "start": 1,
                "pageSize": self.config.batch_size
            }
        }
        
        try:
            response = self._make_request("POST", url, json=payload)
            df = pd.read_csv(pd.io.common.StringIO(response.text))
            logger.info(f"Successfully fetched {len(df)} filings for date range")
            
            # Cache the result
            cache_file = Path(self.config.cache_dir) / f"filings_{start_date}_{end_date}.csv"
            df.to_csv(cache_file, index=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch filings for {start_date} to {end_date}: {e}")
            raise
    
    def fetch_filing_inventory(self) -> pd.DataFrame:
        """
        Fetch the filing inventory (document types and categories)
        """
        logger.info("Fetching filing inventory...")
        
        # This would typically be an Excel download - you may need to adapt based on actual endpoint
        # For now, we'll create a placeholder method
        logger.warning("Filing inventory fetch not yet implemented - requires Excel download handling")
        return pd.DataFrame()
    
    def download_document(self, url: str, document_guid: str) -> bool:
        """
        Download a single document (PDF) from SEDAR+
        """
        local_path = Path(self.config.download_dir) / f"{document_guid}.pdf"
        
        # Skip if already downloaded
        if local_path.exists():
            logger.debug(f"Document {document_guid} already exists, skipping")
            return True
        
        try:
            response = self._make_request("GET", url, timeout=60)
            
            with open(local_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"Downloaded {document_guid}.pdf ({len(response.content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {document_guid}: {e}")
            return False
    
    def download_documents_batch(self, filings_df: pd.DataFrame, max_concurrent: int = 5) -> Dict[str, bool]:
        """
        Download multiple documents with controlled concurrency
        """
        logger.info(f"Starting batch download of {len(filings_df)} documents")
        
        results = {}
        downloaded_count = 0
        
        for idx, row in filings_df.iterrows():
            if 'Generate URL' not in row or 'Document GUID' not in row:
                logger.warning(f"Missing URL or GUID in row {idx}")
                continue
                
            url = row['Generate URL']
            guid = row['Document GUID']
            
            success = self.download_document(url, guid)
            results[guid] = success
            
            if success:
                downloaded_count += 1
            
            # Log progress every 10 downloads
            if (idx + 1) % 10 == 0:
                logger.info(f"Progress: {idx + 1}/{len(filings_df)} documents processed")
        
        logger.info(f"Batch download complete: {downloaded_count}/{len(filings_df)} successful")
        return results
    
    def insert_issuers(self, df: pd.DataFrame) -> bool:
        """
        Insert or update issuer data in the database
        """
        if not self.supabase:
            logger.warning("No Supabase client available, saving to local CSV")
            df.to_csv(Path(self.config.cache_dir) / "issuers_processed.csv", index=False)
            return True
        
        try:
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "issuer_no": str(row["Issuer Number"]),
                    "name": row["Name"],
                    "jurisdiction": row["Jurisdiction(s)"],
                    "issuer_type": row["Type"],
                    "in_default": bool(row["In Default Flag"]),
                    "active_cto": bool(row["Active CTO Flag"]),
                    "updated_at": datetime.utcnow().isoformat()
                })
            
            # Batch insert with upsert
            res = self.supabase.table("dim_issuer").upsert(rows, on_conflict="issuer_no").execute()
            
            if hasattr(res, 'error') and res.error:
                logger.error(f"Error upserting issuers: {res.error}")
                return False
            
            logger.info(f"Successfully upserted {len(rows)} issuers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert issuers: {e}")
            return False
    
    def insert_filings(self, df: pd.DataFrame) -> bool:
        """
        Insert or update filing metadata in the database
        """
        if not self.supabase:
            logger.warning("No Supabase client available, saving to local CSV")
            df.to_csv(Path(self.config.cache_dir) / "filings_processed.csv", index=False)
            return True
        
        try:
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "filing_id": str(uuid.uuid4()),
                    "issuer_no": str(row["Issuer Number"]),
                    "document_guid": row["Document GUID"],
                    "filing_type": row["Filing Type"],
                    "document_type": row["Document Type"],
                    "submitted_date": row["Date Filed"],
                    "url": row["Generate URL"],
                    "size_bytes": row.get("Size", None),
                    "version": row.get("Version", 1),
                    "created_at": datetime.utcnow().isoformat()
                })
            
            # Batch insert with upsert
            res = self.supabase.table("fact_filing").upsert(rows, on_conflict="document_guid").execute()
            
            if hasattr(res, 'error') and res.error:
                logger.error(f"Error upserting filings: {res.error}")
                return False
            
            logger.info(f"Successfully upserted {len(rows)} filings")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert filings: {e}")
            return False
    
    def run_incremental_update(self, days_back: int = 7) -> Dict[str, any]:
        """
        Run an incremental update for the last N days
        """
        logger.info(f"Starting incremental update for last {days_back} days")
        
        results = {
            "start_time": datetime.utcnow().isoformat(),
            "issuers_updated": False,
            "filings_processed": 0,
            "documents_downloaded": 0,
            "errors": []
        }
        
        try:
            # Update issuers (less frequent, but good to refresh)
            issuers_df = self.fetch_issuers_csv()
            results["issuers_updated"] = self.insert_issuers(issuers_df)
            
            # Process filings for each day
            for days_ago in range(days_back):
                date = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                
                try:
                    filings_df = self.fetch_filings_for_date_range(date, date)
                    
                    if len(filings_df) > 0:
                        # Insert filing metadata
                        if self.insert_filings(filings_df):
                            results["filings_processed"] += len(filings_df)
                        
                        # Download documents
                        download_results = self.download_documents_batch(filings_df)
                        results["documents_downloaded"] += sum(download_results.values())
                    
                except Exception as e:
                    error_msg = f"Failed to process date {date}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            results["end_time"] = datetime.utcnow().isoformat()
            logger.info(f"Incremental update complete: {results}")
            
            return results
            
        except Exception as e:
            error_msg = f"Incremental update failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["end_time"] = datetime.utcnow().isoformat()
            return results
    
    def run_historical_backfill(self, start_date: str, end_date: str, chunk_days: int = 30) -> Dict[str, any]:
        """
        Run a historical backfill for a large date range, processing in chunks
        """
        logger.info(f"Starting historical backfill from {start_date} to {end_date}")
        
        results = {
            "start_time": datetime.utcnow().isoformat(),
            "total_filings": 0,
            "total_downloads": 0,
            "chunks_processed": 0,
            "errors": []
        }
        
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            current_dt = start_dt
            
            while current_dt <= end_dt:
                chunk_end = min(current_dt + timedelta(days=chunk_days), end_dt)
                chunk_start_str = current_dt.strftime("%Y-%m-%d")
                chunk_end_str = chunk_end.strftime("%Y-%m-%d")
                
                try:
                    logger.info(f"Processing chunk: {chunk_start_str} to {chunk_end_str}")
                    
                    filings_df = self.fetch_filings_for_date_range(chunk_start_str, chunk_end_str)
                    
                    if len(filings_df) > 0:
                        if self.insert_filings(filings_df):
                            results["total_filings"] += len(filings_df)
                        
                        download_results = self.download_documents_batch(filings_df)
                        results["total_downloads"] += sum(download_results.values())
                    
                    results["chunks_processed"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process chunk {chunk_start_str} to {chunk_end_str}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                
                current_dt = chunk_end + timedelta(days=1)
            
            results["end_time"] = datetime.utcnow().isoformat()
            logger.info(f"Historical backfill complete: {results}")
            
            return results
            
        except Exception as e:
            error_msg = f"Historical backfill failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["end_time"] = datetime.utcnow().isoformat()
            return results

def main():
    """Main execution function"""
    
    # Load configuration from environment
    config = SedarConfig(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
        schema=os.getenv("SUPABASE_SCHEMA", "public"),
        rate_limit_delay=float(os.getenv("RATE_LIMIT_DELAY", "1.0")),
        batch_size=int(os.getenv("BATCH_SIZE", "5000"))
    )
    
    collector = SedarCollector(config)
    
    # Example usage - run incremental update for last 7 days
    results = collector.run_incremental_update(days_back=7)
    
    # Save results
    with open(Path(config.cache_dir) / f"run_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Collection complete. Results: {results}")

if __name__ == "__main__":
    main()