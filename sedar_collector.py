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
        Path(self.config.cache_dir).parent.joinpath("reference").mkdir(parents=True, exist_ok=True) # Added this line
    
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
        logger.info("Fetching filing inventory...")

        FILING_INVENTORY_PATH = Path(self.config.cache_dir).parent / "reference" / "Filing_Inventory.xlsx"
        
        logger.info(f"Expecting Filing_Inventory.xlsx at: {FILING_INVENTORY_PATH}")

        if not FILING_INVENTORY_PATH.exists():
            error_msg = f"Filing_Inventory.xlsx not found at {FILING_INVENTORY_PATH}. Please download the 'Filing Inventory' Excel workbook from the SEDAR+ website and place it at the specified path."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            df = pd.read_excel(FILING_INVENTORY_PATH)
            logger.info(f"Successfully parsed {len(df)} document types from Filing_Inventory.xlsx")
        except Exception as e:
            logger.error(f"Error parsing Filing_Inventory.xlsx: {e}")
            raise

        # Cache the processed data
        cache_file = Path(self.config.cache_dir) / "filing_inventory.csv"
        df.to_csv(cache_file, index=False)
        logger.info(f"Cached filing inventory to {cache_file}")

        return df
    
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

    def insert_document_types(self, df: pd.DataFrame) -> bool:
        """
        Insert or update document type data in the database
        """
        if not self.supabase:
            logger.warning("No Supabase client available, saving document types to local CSV")
            df.to_csv(Path(self.config.cache_dir) / "document_types_processed.csv", index=False)
            return True

        try:
            # Assuming column names from Excel are: 'Filing Category', 'Filing Type', 'Document Type', 'Access Level'
            # Renaming to match schema: 'filing_category', 'filing_type', 'document_type', 'access_level'
            df_renamed = df.rename(columns={
                'Filing Category': 'filing_category',
                'Filing Type': 'filing_type',
                'Document Type': 'document_type',
                'Access Level': 'access_level'
            })

            rows = []
            for _, row in df_renamed.iterrows():
                rows.append({
                    "filing_category": row["filing_category"],
                    "filing_type": row["filing_type"],
                    "document_type": row["document_type"],
                    "access_level": row["access_level"],
                    "updated_at": datetime.utcnow().isoformat()
                })
            
            # Upsert based on a composite unique constraint (filing_category, filing_type, document_type)
            # The constraint name 'document_type_unique_constraint' is assumed to be defined in the DB.
            # If not, Supabase client might allow specifying columns for conflict resolution.
            # For now, using the assumed constraint name.
            # If this causes issues, a fallback could be to use a list of column names for on_conflict
            # e.g., on_conflict=['filing_category', 'filing_type', 'document_type'] if supported by the client version
            res = self.supabase.table("dim_document_type").upsert(
                rows, 
                on_conflict=['filing_category', 'filing_type', 'document_type']
            ).execute()
            
            if hasattr(res, 'error') and res.error:
                logger.error(f"Error upserting document types: {res.error}")
                # Fallback: Try to upsert based on a list of columns if constraint name fails
                # This part needs to be conditional based on the error, or tested if the client supports it.
                # For now, we just log the error and return False.
                # A more robust solution might try a different on_conflict strategy here.
                return False
            
            logger.info(f"Successfully upserted {len(rows)} document types")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert document types: {e}")
            return False

    def fetch_recent_filings_json(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetches recent filings within a given date range and returns them as a list of dictionaries.
        """
        url = f"{self.config.base_url}/csa-party/service/searchDocuments"
        payload = {
            "service": "searchDocuments",
            "queryArgs": {
                "_locale": "en",
                "fromDate": start_date,
                "toDate": end_date,
                "page": 1,
                "pageSize": 1000, # Consider making pageSize configurable
                "sortColumn": "dateFiled",
                "sortOrder": "desc"
            }
        }
        self.logger.info(f"Fetching recent filings JSON from {start_date} to {end_date}")

        try:
            response = self._make_request("POST", url, json=payload)
            response_data = response.json()
        except Exception as e:
            self.logger.error(f"Error fetching or parsing filings JSON: {e}")
            return []

        if not response_data or "results" not in response_data:
            self.logger.error("Failed to fetch filings or no results found in JSON response.")
            return []

        filings = []
        for item in response_data["results"]:
            pdf_url = item.get("generateUrl")
            if not pdf_url:
                # Ensure documentGuid is present before constructing fallback URL
                if item.get("documentGuid"):
                    pdf_url = f"{self.config.base_url}/csa-party/records/document.html?id={item['documentGuid']}"
                else:
                    pdf_url = None # Or some other placeholder if documentGuid is missing
                    self.logger.warning(f"Missing documentGuid for an item, cannot generate fallback URL. Item: {item}")


            filings.append({
                "issuer_no": item.get("issuerNumber"),
                "document_guid": item.get("documentGuid"),
                "date_filed": item.get("dateFiled"), # Keep as string
                "filing_type": item.get("filingType"),
                "document_type": item.get("documentType"),
                "size_bytes": item.get("sizeInBytes"),
                "pdf_url": pdf_url
            })
        
        self.logger.info(f"Retrieved {len(filings)} filings via JSON endpoint.")
        return filings

    def download_pdf_to_bytes(self, pdf_url: str) -> Optional[bytes]:
        """
        Downloads a PDF from the given URL and returns its content as bytes.
        """
        self.logger.info(f"Attempting to download PDF from URL: {pdf_url}")
        try:
            # _make_request handles rate limiting, retries, and basic error logging.
            # stream=True is important for efficient handling of potentially large files.
            response = self._make_request("GET", pdf_url, stream=True, timeout=60)
            
            # _make_request raises an exception on HTTP error status, so if we get here,
            # the request was successful in terms of HTTP status codes.
            
            pdf_bytes = response.content
            self.logger.info(f"Successfully downloaded {len(pdf_bytes)} bytes from {pdf_url}")
            return pdf_bytes
        except requests.exceptions.RequestException as e:
            # _make_request already logs the error, but we can add context here.
            self.logger.error(f"Failed to download PDF from {pdf_url}: {e}")
            # Let the exception propagate to be handled by the caller,
            # or return None if specific handling is preferred here.
            # For now, re-raising to ensure caller is aware.
            raise
        except Exception as e:
            # Catch any other unexpected errors
            self.logger.error(f"An unexpected error occurred while downloading PDF from {pdf_url}: {e}")
            raise

    def insert_filing_with_pdf(self, filing_data: Dict[str, Any], pdf_bytes: bytes) -> bool:
        """
        Inserts a filing record along with its PDF data into the Supabase 'filings' table.
        """
        if not self.supabase:
            self.logger.warning("Supabase client not available. Skipping database insertion of filing with PDF.")
            return False

        document_guid = filing_data.get("document_guid")
        if not document_guid:
            self.logger.error("Cannot insert filing: document_guid is missing from filing_data.")
            return False

        try:
            # Ensure date_filed is in 'YYYY-MM-DD' format.
            # The date from SEDAR+ is usually "YYYY-MM-DDTHH:MM:SSZ" or "YYYY-MM-DD".
            # We only need the date part.
            date_filed_raw = filing_data.get("date_filed")
            if date_filed_raw:
                date_filed = date_filed_raw.split('T')[0]
            else:
                self.logger.warning(f"date_filed is missing for document_guid: {document_guid}. Setting to None.")
                date_filed = None


            row_data = {
                "issuer_no": filing_data.get("issuer_no"),
                "document_guid": document_guid,
                "date_filed": date_filed,
                "filing_type": filing_data.get("filing_type"),
                "document_type": filing_data.get("document_type"),
                "size_bytes": filing_data.get("size_bytes"),
                "pdf_data": pdf_bytes  # Supabase client handles bytes for BYTEA columns
            }

            self.logger.info(f"Attempting to upsert filing {document_guid} with PDF data.")
            
            # Upsert into the 'filings' table
            res = self.supabase.table("filings").upsert(row_data, on_conflict="document_guid").execute()

            # Check for errors (compatibility with different supabase-py versions)
            if hasattr(res, 'error') and res.error:
                self.logger.error(f"Error upserting filing {document_guid}: {res.error}")
                return False
            # For newer versions, data might be empty or contain an error indication if not successful
            if not res.data and not (hasattr(res, 'status_code') and 200 <= res.status_code < 300): # Check status_code for v2
                 self.logger.error(f"Failed to upsert filing {document_guid}. Response: {res}")
                 return False


            self.logger.info(f"Successfully upserted filing {document_guid} with PDF data.")
            return True

        except Exception as e:
            self.logger.error(f"An exception occurred while inserting filing {document_guid} with PDF: {e}")
            return False

    def update_reference_data(self) -> Dict[str, any]:
        """
        Fetches and updates reference data: issuers and document types.
        """
        logger.info("Starting reference data update process...")
        results = {
            "start_time": datetime.utcnow().isoformat(),
            "issuers_fetched": 0,
            "issuers_inserted_successfully": False,
            "document_types_fetched": 0,
            "document_types_inserted_successfully": False,
            "errors": [],
            "end_time": None
        }

        # Update issuers
        try:
            logger.info("Attempting to fetch and insert issuers...")
            issuers_df = self.fetch_issuers_csv()
            results["issuers_fetched"] = len(issuers_df)
            if results["issuers_fetched"] > 0:
                if self.insert_issuers(issuers_df):
                    results["issuers_inserted_successfully"] = True
                    logger.info("Issuers updated successfully.")
                else:
                    results["errors"].append("Failed to insert issuers into database.")
                    logger.error("Failed to insert issuers into database.")
            else:
                logger.info("No issuers fetched or an error occurred during fetch.")
        except Exception as e:
            error_msg = f"Error during issuer update: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        # Update document types from Filing Inventory
        try:
            logger.info("Attempting to fetch and insert document types from Filing Inventory...")
            doc_types_df = self.fetch_filing_inventory()
            results["document_types_fetched"] = len(doc_types_df)
            if results["document_types_fetched"] > 0:
                if self.insert_document_types(doc_types_df):
                    results["document_types_inserted_successfully"] = True
                    logger.info("Document types updated successfully from Filing Inventory.")
                else:
                    results["errors"].append("Failed to insert document types into database.")
                    logger.error("Failed to insert document types into database.")
            else:
                logger.info("No document types fetched from Filing Inventory or an error occurred during fetch.")
        except FileNotFoundError as fnf_error:
            error_msg = f"Filing Inventory file not found: {fnf_error}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Error during document type update: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        results["end_time"] = datetime.utcnow().isoformat()
        logger.info(f"Reference data update process finished. Results: {results}")
        return results
    
    def run_incremental_update(self, days_back: int = 1) -> Dict[str, any]: # Default to 1 day as per typical incremental use
        """
        Run an incremental update for the last N days using JSON fetching and PDF byte storage.
        """
        logger.info(f"Starting incremental update for the last {days_back} day(s) using JSON/PDF byte workflow.")
        
        results = {
            "start_time": datetime.utcnow().isoformat(),
            "issuers_updated": False,
            "total_filings_retrieved_json": 0,
            "total_pdfs_downloaded_to_memory": 0,
            "total_filings_inserted_with_pdf": 0,
            "errors": []
        }
        
        try:
            # Update issuers (can remain, good practice)
            try:
                logger.info("Attempting to refresh issuer data...")
                issuers_df = self.fetch_issuers_csv()
                if issuers_df is not None and not issuers_df.empty:
                    results["issuers_updated"] = self.insert_issuers(issuers_df)
                    logger.info(f"Issuer data refresh status: {results['issuers_updated']}")
                else:
                    logger.warning("No issuer data fetched, skipping issuer update.")
                    results["issuers_updated"] = False
            except Exception as e:
                error_msg = f"Error during issuer data refresh: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["issuers_updated"] = False

            # Process filings for each day in the specified range
            for days_ago in range(days_back):
                target_date = datetime.utcnow() - timedelta(days=days_ago)
                target_date_str = target_date.strftime("%Y-%m-%d")
                logger.info(f"--- Starting processing for date: {target_date_str} ---") # Enhanced log statement

                try:
                    # 1. Fetch recent filings metadata using the JSON endpoint
                    filings_metadata = self.fetch_recent_filings_json(start_date=target_date_str, end_date=target_date_str)
                    results["total_filings_retrieved_json"] += len(filings_metadata)
                    logger.info(f"Retrieved {len(filings_metadata)} filing metadata entries for {target_date_str}.")

                    if not filings_metadata:
                        logger.info(f"No filings found for {target_date_str}.")
                        continue

                    for filing_data in filings_metadata:
                        document_guid = filing_data.get("document_guid")
                        pdf_url = filing_data.get("pdf_url")

                        if not document_guid or not pdf_url:
                            logger.warning(f"Skipping filing due to missing document_guid or pdf_url: {filing_data}")
                            results["errors"].append(f"Skipped filing (missing guid/url): {filing_data.get('issuer_no', 'N/A')}-{document_guid}")
                            continue
                        
                        logger.info(f"Processing filing: {document_guid} from URL: {pdf_url}")

                        try:
                            # 2. Download PDF to bytes
                            pdf_bytes = self.download_pdf_to_bytes(pdf_url=pdf_url)

                            if pdf_bytes:
                                results["total_pdfs_downloaded_to_memory"] += 1
                                # 3. Insert filing metadata and PDF bytes into database
                                if self.insert_filing_with_pdf(filing_data=filing_data, pdf_bytes=pdf_bytes):
                                    results["total_filings_inserted_with_pdf"] += 1
                                else:
                                    logger.error(f"Failed to insert filing {document_guid} with PDF into database.")
                                    results["errors"].append(f"DB Insert Failed: {document_guid}")
                            else:
                                logger.warning(f"Failed to download PDF for {document_guid} from {pdf_url}. Skipping database insertion.")
                                results["errors"].append(f"PDF Download Failed: {document_guid}")

                        except Exception as e:
                            error_msg = f"Error processing filing {document_guid} (URL: {pdf_url}): {e}"
                            logger.error(error_msg)
                            results["errors"].append(error_msg)
                            # Continue to the next filing

                except Exception as e:
                    error_msg = f"Failed to process filings for date {target_date_str}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            results["end_time"] = datetime.utcnow().isoformat()
            logger.info(f"Incremental update complete. Results: {results}")
            return results
            
        except Exception as e: # Catch-all for the entire method
            error_msg = f"Critical error in incremental update process: {e}"
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

    # Scheduling Information:
    # This script can be scheduled to run regularly (e.g., every 15 minutes or hourly)
    # using cron, Windows Task Scheduler, or a workflow orchestrator like Apache Airflow.
    # Example cron job to run every 15 minutes:
    # */15 * * * * /usr/bin/python3 /path/to/your_virtualenv/bin/python /path/to/sedar_collector.py >> /path/to/sedar_collector_cron.log 2>&1
    # Ensure environment variables (SUPABASE_URL, SUPABASE_KEY, etc.) are available to the cron environment
    # or are loaded within the script (e.g., using a .env file and python-dotenv if not already handled).
    # Consider the API rate limits and the frequency of new filings when choosing the schedule.
    # Running too frequently (e.g., every minute) might not be necessary and could strain the API.
    # Hourly or every 15-30 minutes is likely a reasonable starting point for incremental updates.

    # Update reference data (e.g., list of issuers, document types)
    # This might not need to run as frequently as the incremental filing check.
    # Could be daily or even less frequent depending on how often this data changes.
    logger.info("Starting reference data update...")
    ref_data_results = collector.update_reference_data()
    ref_results_path = Path(config.cache_dir) / f"reference_update_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(ref_results_path, "w") as f:
        json.dump(ref_data_results, f, indent=2, default=str)
    logger.info(f"Reference data update complete. Results saved to {ref_results_path}")
    print(f"Reference data update complete. See logs and {ref_results_path} for details.")

    # Example usage - run incremental update for the last 2 days (e.g., today and yesterday)
    # This uses the new JSON/PDF byte workflow.
    # Adjust `days_back` based on how reliably the script runs and potential catch-up needs.
    # If running every 15 mins, `days_back=1` (for today) might be sufficient most of the time,
    # but `days_back=2` provides a small buffer.
    logger.info("Starting incremental update for recent filings (e.g., last 2 days)...")
    incremental_results = collector.run_incremental_update(days_back=2) 
    
    incremental_results_path = Path(config.cache_dir) / f"incremental_run_results_json_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(incremental_results_path, "w") as f:
        json.dump(incremental_results, f, indent=2, default=str) # Use default=str for datetime if any
    logger.info(f"Incremental collection complete. Results saved to {incremental_results_path}")
    print(f"Incremental collection complete. Results: {incremental_results}")


if __name__ == "__main__":
    main()