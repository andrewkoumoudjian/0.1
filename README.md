# SEDAR+ Data Collection System

## Overview
`sedar_collector.py` is a Python script designed to collect and manage financial data from SEDAR+ (System for Electronic Document Analysis and Retrieval Plus). It automates the process of fetching information about reporting issuers, their public filings, and specific document types. The collected data can be stored locally as CSV files and downloaded PDFs, and/or uploaded to a configured Supabase PostgreSQL database for further analysis and use.

## Features
- **Issuer Data**: Fetches and stores a complete list of Canadian reporting issuers.
- **Filing Metadata**: Retrieves metadata for public filings.
    - **Incremental Updates (JSON API)**: Uses SEDAR+'s `searchDocuments` JSON API to fetch recent filings, including direct PDF URLs.
    - **Historical Backfill (CSV Export)**: Uses SEDAR+'s CSV export feature for bulk fetching of historical filing metadata.
- **PDF Document Storage**:
    - For incremental updates, downloads PDF documents and stores their raw byte content directly in the `filings.pdf_data` database column.
    - For historical backfill, continues to download PDFs to the local file system (`data/pdfs/`).
- **Filing Inventory**: Processes the manually downloaded "Filing Inventory" Excel file to map document categories and types.
- **Supabase Integration**: Optionally uploads and synchronizes data with a Supabase PostgreSQL database, including the new `filings` table with embedded PDF data.
- **Local Caching**: Caches fetched data (issuers, CSV-based filings, document types) locally to minimize redundant downloads and API calls.
- **Rate Limiting**: Implements configurable delays between requests to SEDAR+ to ensure respectful data collection.
- **Retry Logic**: Automatically retries failed network requests.
- **Workflow Functions**:
    - `update_reference_data()`: Updates issuer information and document type definitions from the Filing Inventory.
    - `run_incremental_update()`: Fetches recent filings (using JSON API), downloads their PDFs directly into the database, for a specified number of recent days. This is the primary method for ongoing data collection.
    - `run_historical_backfill()`: Allows for bulk collection of filings (CSV based) and documents (to local filesystem) for a specified historical date range.
- **Logging**: Comprehensive logging of script activities, errors, and progress.

## Revised Data Collection (JSON API and PDF Storage) - For Incremental Updates

The `sedar_collector.py` script has been enhanced for incremental updates to use a more direct and robust method for fetching recent filings and their PDF documents:

1.  **JSON API for Recent Filings**: Instead of relying on daily CSV exports for recent data, the `run_incremental_update` function now queries the SEDAR+ `searchDocuments` JSON API. This provides more structured metadata directly from the source.
2.  **Direct PDF Download to Database**:
    *   For each filing retrieved via the JSON API, the script attempts to download the associated PDF document.
    *   The raw binary content (bytes) of the PDF is then stored in the `pdf_data` column (type `BYTEA`) of the new `filings` table in the Supabase database.
    *   This approach keeps the metadata and the actual document data together in the database, simplifying data management for recent filings.
3.  **`filings` Table**: A new table schema is defined in `new_filings_schema.sql` for this purpose.
    *   **Key Columns**:
        *   `filing_id` (UUID, Primary Key)
        *   `issuer_no` (TEXT)
        *   `document_guid` (TEXT, Unique): Crucial for identifying and de-duplicating filings.
        *   `date_filed` (DATE)
        *   `filing_type` (TEXT)
        *   `document_type` (TEXT)
        *   `size_bytes` (BIGINT)
        *   `pdf_data` (BYTEA): Stores the raw binary content of the downloaded PDF.
4.  **Benefits**:
    *   More reliable data fetching for recent items.
    *   Consolidated storage of metadata and PDF content for easier access and analysis.
    *   Reduced reliance on parsing CSV files for the most current data.

The historical backfill (`run_historical_backfill`) continues to use the CSV export method and saves PDFs to the local filesystem, as this is more suitable for very large historical data pulls.

## Prerequisites
- Python 3.7+
- Python dependencies (install via `pip install -r requirements.txt`):
    - `requests>=2.31.0`
    - `pandas>=2.0.0`
    - `supabase>=1.0.0`
    - `urllib3>=2.0.0`
    - `numpy>=1.24.0`
    - `python-dateutil>=2.8.0`
    - `python-dotenv>=1.0.0` (for managing environment variables)

## Setup and Configuration

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Variables**:
    Create a `.env` file in the root of the project directory by copying `example.env` (if provided) or creating a new one. Populate it with the following variables:

    *   `SEDAR_BASE_URL`: The base URL for the SEDAR+ API (e.g., `https://www.sedarplus.ca`). **Required.**
    *   `SUPABASE_URL`: Your Supabase project URL. **Required if using Supabase integration.**
    *   `SUPABASE_KEY`: Your Supabase project API key (anon or service role). **Required if using Supabase integration.**
    *   `SUPABASE_SCHEMA`: The Supabase database schema to use.
        *   Default: `public`
        *   Purpose: Specifies the target schema in your Supabase database.
    *   `RATE_LIMIT_DELAY`: Delay in seconds between consecutive requests to SEDAR+.
        *   Default: `1.0`
        *   Purpose: Ensures respectful data collection and avoids overwhelming the SEDAR+ servers.
    *   `BATCH_SIZE`: Number of records to fetch per API call for paginated results (e.g., when fetching filings).
        *   Default: `5000`
        *   Purpose: Controls the size of data chunks fetched from SEDAR+.
    *   `MAX_RETRIES`: Number of retry attempts for failed network requests.
        *   Default: `3`
        *   Purpose: Improves script resilience against transient network issues.
    *   `DOWNLOAD_DIR`: Local directory to store downloaded PDF documents.
        *   Default: `./data/pdfs`
        *   Purpose: Defines where filing documents are saved.
    *   `CACHE_DIR`: Local directory to store cached CSV data (issuers, filings, etc.).
        *   Default: `./data/cache`
        *   Purpose: Stores intermediate data to speed up subsequent runs and reduce API calls.

4.  **Manual Setup - Filing Inventory**:
    The script requires the "Filing Inventory" Excel file from SEDAR+ to correctly map and categorize document types. This file must be downloaded manually.

    *   **What it is**: The Filing Inventory provides a comprehensive list of filing categories, filing types, and document types used on SEDAR+.
    *   **Why it's needed**: `sedar_collector.py` uses this file to populate the `dim_document_type` table in the database (if configured) and to understand the structure of available documents.
    *   **How to get it**:
        1.  Go to the SEDAR+ website ([https://www.sedarplus.ca/](https://www.sedarplus.ca/)).
        2.  Look for a section typically named "SEDAR+ User Resources," "Help," "Tools," or "Reference Materials." The "Filing Inventory" Excel workbook is usually found there. (The exact location may change, so you might need to browse the site).
        3.  Download the Excel file. It is often named `Filing_Inventory.xlsx` or similar.
    *   **Where to place it**:
        1.  Rename the downloaded file to `Filing_Inventory.xlsx`.
        2.  Place this file in the `data/reference/` directory at the root of the project.
            ```
            YourProjectRoot/
            ├── data/
            │   └── reference/
            │       └── Filing_Inventory.xlsx
            ├── sedar_collector.py
            └── ... other files
            ```
        3.  The script will attempt to create the `data/reference/` directory if it doesn't exist when `update_reference_data()` is run. However, it's good practice to ensure it's there.

## Running the Script

Execute the script from the project's root directory:
```bash
python sedar_collector.py
```

By default, the `main()` function in `sedar_collector.py` performs the following actions:
1.  Calls `collector.update_reference_data()`: This fetches the latest issuer data from SEDAR+ and processes the local `Filing_Inventory.xlsx` file.
2.  Calls `collector.run_incremental_update(days_back=2)`: This fetches recent filings for the last 2 days (today and yesterday) using the new JSON API method, downloads their PDFs, and stores them in the `filings` table in Supabase.

**Scheduling the Script**:
As noted in `sedar_collector.py`, the script is designed for regular execution to keep your data current.
-   Use cron (Linux/macOS), Windows Task Scheduler, or a workflow orchestrator (e.g., Apache Airflow).
-   Example cron job to run every 15 minutes:
    ```cron
    */15 * * * * /path/to/your_virtualenv/bin/python /path/to/sedar_collector.py >> /path/to/sedar_collector_cron.log 2>&1
    ```
-   Ensure environment variables (`SUPABASE_URL`, `SUPABASE_KEY`, etc.) are available to the execution environment.

**Output Data Storage**:
*   **Logs**: Script activities and errors are logged to `sedar_collector.log` and also printed to the console.
*   **Cached Files**: CSV files for issuers, historical filings, and processed filing inventory are stored in `data/cache/`.
*   **Downloaded PDFs (Historical)**: PDF documents from `run_historical_backfill` are saved in `data/pdfs/`. PDFs from `run_incremental_update` are stored directly in the database.
*   **Results Files**: JSON files summarizing the outcomes of operations like `update_reference_data` or `run_incremental_update` are saved in `data/cache/`.

## Workflow Functions

The `SedarCollector` class provides several main workflow methods:

*   **`update_reference_data()`**:
    *   **Purpose**: Fetches and updates essential reference datasets (issuers, document types from `Filing_Inventory.xlsx`).
    *   Run periodically to keep reference information current.

*   **`run_incremental_update(days_back: int = 2)`**:
    *   **Purpose**: Collects recent filings using the JSON API and stores them with their PDF content in the database.
    *   Fetches filing metadata for the last `days_back` days.
    *   Downloads the PDF documents and stores their byte data in the `filings.pdf_data` column.
    *   This is the **primary method for ongoing, automated data collection**.

*   **`run_historical_backfill(start_date: str, end_date: str, chunk_days: int = 30)`**:
    *   **Purpose**: Performs bulk collection of filings (CSV-based) and documents (to local filesystem) for a specified historical period.
    *   Useful for initially populating your database or collecting data for specific historical research where PDFs are stored locally.

## Database Schema

If Supabase is configured, the script interacts with a PostgreSQL database. The schema is primarily defined in two files:

1.  **`new_filings_schema.sql`**:
    *   Defines the **`filings` table**, which is central to the new data collection approach.
    *   **Key columns**: `filing_id` (PK), `issuer_no`, `document_guid` (Unique), `date_filed`, `filing_type`, `document_type`, `size_bytes`, and `pdf_data` (BYTEA).
    *   This table stores metadata for filings fetched via the JSON API and embeds their PDF content directly in the `pdf_data` column.

2.  **`database_schema.sql`**:
    *   Defines other related tables used by the system, such as:
        *   `public.dim_issuer`: Stores detailed information about each reporting issuer.
        *   `public.dim_document_type`: Stores information about filing categories and types from `Filing_Inventory.xlsx`.
        *   `public.fact_filing`: This table was previously used for all filing metadata. While `run_historical_backfill` might still interact with it or a similar structure for CSV-based data, new incremental filings with embedded PDFs go into the `filings` table defined in `new_filings_schema.sql`. The system might evolve to consolidate these, but for now, they serve distinct data ingestion paths.
    *   It also includes placeholder tables for future extensions (e.g., `fact_statement_line`, `mart_sentiment`).

**Note on Data Flow**:
-   **Recent Filings (Incremental)**: `searchDocuments` JSON API -> `SedarCollector.fetch_recent_filings_json()` -> `SedarCollector.download_pdf_to_bytes()` -> `SedarCollector.insert_filing_with_pdf()` -> `filings` table (with `pdf_data`).
-   **Historical Filings (Bulk)**: CSV Export -> `SedarCollector.fetch_filings_for_date_range()` -> (PDFs to local disk via `download_documents_batch`) -> `dim_issuer`, `fact_filing` (metadata only, PDF path might be stored if adapted).

## Data Storage

*   **Local Cache (`data/cache/`)**:
    *   `issuers_{timestamp}.csv`: Raw list of issuers from SEDAR+.
    *   `filings_{start_date}_{end_date}.csv`: Raw list of *historical* filings for a given period (CSV based).
    *   `filing_inventory.csv`: Processed data from `Filing_Inventory.xlsx`.
    *   Results files for operations (`*_results_{timestamp}.json`).
*   **PDF Downloads (`data/pdfs/`)**: Stores PDF documents downloaded by the `run_historical_backfill` process. PDFs from `run_incremental_update` are now stored in the database.
*   **Supabase Database**:
    *   **`filings` table**: Stores recent filings with embedded PDF data (from `run_incremental_update`).
    *   Other tables like `dim_issuer`, `dim_document_type`, and potentially an older `fact_filing` table for historical CSV-based metadata.

## Compliance and Best Practices

*   **Respectful Collection**: The script defaults to a `RATE_LIMIT_DELAY` of 1.0 second between requests to SEDAR+. Please maintain or increase this delay to avoid overloading the SEDAR+ servers.
*   **User-Agent**: The script identifies itself with the User-Agent `SedarAnalytics/1.0 (Educational Research)`.
*   **Terms of Use**: Users are responsible for ensuring their use of data collected from SEDAR+ complies with all applicable terms of service and regulations.

## Troubleshooting

*   **`FileNotFoundError` for `Filing_Inventory.xlsx`**:
    *   This means the script could not find `data/reference/Filing_Inventory.xlsx`.
    *   Ensure you have manually downloaded this file from SEDAR+ and placed it in the correct directory with the correct name. See the "Manual Setup - Filing Inventory" section.
*   **Supabase Connection Errors**:
    *   Verify that `SUPABASE_URL` and `SUPABASE_KEY` in your `.env` file are correct and that they are accessible to the script's execution environment (especially for cron jobs).
    *   Check your Supabase project status and network connectivity.
    *   Ensure the tables defined in `database_schema.sql` and `new_filings_schema.sql` have been created in your Supabase database.
*   **Permission Errors**:
    *   Ensure the script has write permissions for the `data/` directory (and its subdirectories: `cache/`, `reference/`, `pdfs/` if still used by historical runs) and for `sedar_collector.log`.
*   **Rate Limiting Issues (429 Errors)**:
    *   If you encounter errors related to too many requests, increase the `RATE_LIMIT_DELAY` in your `.env` file.

## Extending the System
The current system provides a solid foundation for data collection. Future extensions could include:
-   Automated PDF text extraction and NLP processing.
-   Integration with other data sources like SEDI for insider trading information.
-   Advanced data warehousing and analytical marts.
-   A web interface for data exploration and visualization.

## License
This project is intended for educational and research purposes. Users must ensure their use of data collected via this script complies with all SEDAR+ terms of use and any relevant data privacy or protection regulations.
