# SEDAR+ Data Collection System

## Overview
`sedar_collector.py` is a Python script designed to collect and manage financial data from SEDAR+ (System for Electronic Document Analysis and Retrieval Plus). It automates the process of fetching information about reporting issuers, their public filings, and specific document types. The collected data can be stored locally as CSV files and downloaded PDFs, and/or uploaded to a configured Supabase PostgreSQL database for further analysis and use.

## Features
- **Issuer Data**: Fetches and stores a complete list of Canadian reporting issuers.
- **Filing Metadata**: Retrieves metadata for all public filings.
- **Filing Inventory**: Processes the manually downloaded "Filing Inventory" Excel file to map document categories and types.
- **Document Downloads**: Automates the download of PDF documents associated with filings.
- **Supabase Integration**: Optionally uploads and synchronizes data with a Supabase PostgreSQL database.
- **Local Caching**: Caches fetched data (issuers, filings, document types) locally to minimize redundant downloads and API calls.
- **Rate Limiting**: Implements configurable delays between requests to SEDAR+ to ensure respectful data collection.
- **Retry Logic**: Automatically retries failed network requests.
- **Workflow Functions**:
    - `update_reference_data()`: Updates issuer information and document type definitions from the Filing Inventory.
    - `run_incremental_update()`: Fetches recent filings and their associated documents for a specified number of days.
    - `run_historical_backfill()`: Allows for bulk collection of filings and documents for a specified historical date range.
- **Logging**: Comprehensive logging of script activities, errors, and progress.

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

    *   `SEDAR_BASE_URL`: The base URL for the SEDAR+ API.
        *   Default: `https://www.sedarplus.ca`
        *   Purpose: Specifies the SEDAR+ service endpoint.
    *   `SUPABASE_URL`: (Optional) Your Supabase project URL.
        *   Purpose: Enables data synchronization with your Supabase database. If not provided, data is only stored locally.
    *   `SUPABASE_KEY`: (Optional) Your Supabase project API key (anon or service role).
        *   Purpose: Authenticates with your Supabase project.
    *   `SUPABASE_SCHEMA`: (Optional) The Supabase database schema to use.
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

By default, the `main()` function in `sedar_collector.py` currently performs the following actions:
1.  Calls `collector.update_reference_data()`: This fetches the latest issuer data from SEDAR+ and processes the local `Filing_Inventory.xlsx` file. Results are saved to `reference_update_results_{timestamp}.json` in the cache directory.
2.  The call to `collector.run_incremental_update()` might be commented out by default in `main()`. If you wish to run it, you can uncomment it. This function fetches filings for the last 7 days (by default).

**Output Data Storage**:
*   **Logs**: Script activities and errors are logged to `sedar_collector.log` and also printed to the console.
*   **Cached Files**: CSV files for issuers, filings, and processed filing inventory are stored in `data/cache/`.
*   **Downloaded PDFs**: PDF documents are saved in `data/pdfs/`.
*   **Results Files**: JSON files summarizing the outcomes of operations like `update_reference_data` or `run_incremental_update` are saved in `data/cache/`.

## Workflow Functions

The `SedarCollector` class provides several main workflow methods:

*   **`update_reference_data()`**:
    *   **Purpose**: Fetches and updates essential reference datasets.
    *   It retrieves the latest list of all reporting issuers from SEDAR+.
    *   It processes the `Filing_Inventory.xlsx` file (which you must manually download and place in `data/reference/`) to update the database with document types, categories, and access levels.
    *   This function should be run periodically to keep your issuer and document type information current.

*   **`run_incremental_update(days_back: int = 7)`**:
    *   **Purpose**: Collects recent filings and their associated documents.
    *   Fetches filing metadata for the last `days_back` days.
    *   Downloads the PDF documents for these filings.
    *   Ideal for regular, automated runs (e.g., daily) to keep your dataset up-to-date.

*   **`run_historical_backfill(start_date: str, end_date: str, chunk_days: int = 30)`**:
    *   **Purpose**: Performs bulk collection of filings and documents for a specified historical period.
    *   Fetches filing metadata in chunks of `chunk_days` to manage large data volumes.
    *   Downloads associated PDF documents.
    *   Useful for initially populating your database or collecting data for specific historical research.

## Database Schema

If Supabase is configured, the script will attempt to store data in a PostgreSQL database adhering to the schema defined in `database_schema.sql`.

**Key Tables**:
*   `public.dim_issuer`: Stores detailed information about each reporting issuer (e.g., name, jurisdiction, type). Primary Key: `issuer_no`.
*   `public.dim_document_type`: Stores information about filing categories, filing types, and document types, sourced from the `Filing_Inventory.xlsx`. Primary Key: `document_type_id` (surrogate), Unique Constraint: (`filing_category`, `filing_type`, `document_type`).
*   `public.fact_filing`: Contains metadata for each individual filing (e.g., issuer, document GUID, submission date, download URL, size). Primary Key: `filing_id` (UUID), Unique Constraint: `document_guid`.

Other tables like `fact_statement_line`, `fact_insider_tx`, `mart_sentiment`, etc., are defined in `database_schema.sql` for potential future extensions (e.g., NLP analysis, financial data extraction).

## Data Storage

*   **Local Cache (`data/cache/`)**:
    *   `issuers_{timestamp}.csv`: Raw list of issuers from SEDAR+.
    *   `filings_{start_date}_{end_date}.csv`: Raw list of filings for a given period.
    *   `filing_inventory.csv`: Processed data from `Filing_Inventory.xlsx`.
    *   `issuers_processed.csv`: Issuers data prepared for Supabase (if Supabase is off).
    *   `filings_processed.csv`: Filings data prepared for Supabase (if Supabase is off).
    *   `document_types_processed.csv`: Document types data prepared for Supabase (if Supabase is off).
    *   `*_results_{timestamp}.json`: JSON files detailing the outcome of major operations.
*   **PDF Downloads (`data/pdfs/`)**: Stores downloaded PDF documents, named by their `Document GUID`.
*   **Supabase (Optional)**: If `SUPABASE_URL` and `SUPABASE_KEY` are provided, the script will attempt to upsert data into the tables defined in `database_schema.sql`.

## Compliance and Best Practices

*   **Respectful Collection**: The script defaults to a `RATE_LIMIT_DELAY` of 1.0 second between requests to SEDAR+. Please maintain or increase this delay to avoid overloading the SEDAR+ servers.
*   **User-Agent**: The script identifies itself with the User-Agent `SedarAnalytics/1.0 (Educational Research)`.
*   **Terms of Use**: Users are responsible for ensuring their use of data collected from SEDAR+ complies with all applicable terms of service and regulations.

## Troubleshooting

*   **`FileNotFoundError` for `Filing_Inventory.xlsx`**:
    *   This means the script could not find `data/reference/Filing_Inventory.xlsx`.
    *   Ensure you have manually downloaded this file from SEDAR+ and placed it in the correct directory with the correct name. See the "Manual Setup - Filing Inventory" section.
*   **Supabase Connection Errors**:
    *   Verify that `SUPABASE_URL` and `SUPABASE_KEY` in your `.env` file are correct.
    *   Check your Supabase project status and network connectivity.
    *   Ensure the tables defined in `database_schema.sql` have been created in your Supabase database.
*   **Permission Errors**:
    *   Ensure the script has write permissions for the `data/` directory (and its subdirectories: `cache/`, `reference/`, `pdfs/`) and for `sedar_collector.log`.
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
