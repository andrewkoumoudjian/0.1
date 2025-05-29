# SEDAR+ Data Collection System

A comprehensive Python-based system for collecting, processing, and storing Canadian financial data from SEDAR+ (System for Electronic Document Analysis and Retrieval Plus).

## Overview

This system implements the data collection layer of a Canadian financial data platform, following the architectural principles outlined in the technical blueprint. It provides:

- **Respectful data collection** with rate limiting and error handling
- **Scalable architecture** supporting both incremental and historical data collection
- **Robust storage** with local caching and optional database integration
- **Compliance-focused design** adhering to SEDAR+ terms of use

## Quick Start

### 1. Installation

```bash
# Clone or download the project files
# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the `.env` file and update with your settings:

```bash
# Required: SEDAR+ base URL (usually no change needed)
SEDAR_BASE_URL=https://www.sedarplus.ca

# Optional: Supabase database (if not provided, data saves locally)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
SUPABASE_SCHEMA=public

# Collection settings (adjust based on your needs)
RATE_LIMIT_DELAY=1.0          # Be respectful - 1 second between requests
BATCH_SIZE=5000               # Records per request
```

### 3. Database Setup (Optional)

If using Supabase or PostgreSQL:

```bash
# Execute the schema in your database
psql -d your_database -f database_schema.sql
```

### 4. Run Collection

```python
# Basic usage - collect last 7 days of data
python sedar_collector.py

# Or use the API programmatically
from sedar_collector import SedarCollector, SedarConfig

config = SedarConfig()
collector = SedarCollector(config)

# Run incremental update
results = collector.run_incremental_update(days_back=7)
print(f"Processed {results['filings_processed']} filings")
```

## Features

### Data Collection Capabilities

- **Issuer Data**: Complete list of Canadian reporting issuers
- **Filing Metadata**: All document types (financial statements, MD&As, press releases, etc.)
- **Document Downloads**: Automated PDF retrieval with progress tracking
- **Incremental Updates**: Daily collection of new filings
- **Historical Backfill**: Bulk collection for date ranges

### Technical Features

- **Rate Limiting**: Configurable delays between requests
- **Retry Logic**: Automatic retries with exponential backoff
- **Error Handling**: Comprehensive logging and error recovery
- **Caching**: Local CSV caching to avoid re-requests
- **Progress Tracking**: Detailed logging and progress reports

### Data Storage

- **Local Storage**: CSV files and PDFs saved locally
- **Database Integration**: Optional Supabase/PostgreSQL storage
- **Schema Design**: Normalized tables following data warehouse patterns
- **Version Control**: Handles amended filings and superseded documents

## Architecture

The system follows a layered architecture:

```
┌─────────────────┐
│   SEDAR+ API    │ ← Web scraping with respectful rate limiting
└─────────────────┘
         │
┌─────────────────┐
│  Data Collection │ ← SedarCollector class with retry logic
└─────────────────┘
         │
┌─────────────────┐
│     Caching     │ ← Local CSV files for resilience
└─────────────────┘
         │
┌─────────────────┐
│    Database     │ ← PostgreSQL with dimensional modeling
└─────────────────┘
```

## Usage Examples

### Collect Recent Data
```python
from sedar_collector import SedarCollector, SedarConfig

config = SedarConfig(rate_limit_delay=1.0)
collector = SedarCollector(config)

# Get last 30 days of filings
results = collector.run_incremental_update(days_back=30)
```

### Historical Backfill
```python
# Collect 2023 data in monthly chunks
results = collector.run_historical_backfill(
    start_date="2023-01-01",
    end_date="2023-12-31",
    chunk_days=30
)
```

### Issuer Data Only
```python
# Just get the current issuer list
issuers_df = collector.fetch_issuers_csv()
print(f"Found {len(issuers_df)} Canadian issuers")
```

### Custom Date Range
```python
# Get filings for specific dates
filings_df = collector.fetch_filings_for_date_range("2024-01-01", "2024-01-31")
collector.download_documents_batch(filings_df)
```

## Data Schema

The system creates several tables following dimensional modeling:

- **`dim_issuer`**: Company/issuer information
- **`fact_filing`**: Filing metadata and documents
- **`fact_statement_line`**: Financial statement data (future)
- **`fact_insider_tx`**: Insider trading data (future)
- **`mart_sentiment`**: NLP analysis results (future)

See `database_schema.sql` for complete schema.

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `SEDAR_BASE_URL` | SEDAR+ API base URL | `https://www.sedarplus.ca` |
| `RATE_LIMIT_DELAY` | Seconds between requests | `1.0` |
| `BATCH_SIZE` | Records per API call | `5000` |
| `MAX_RETRIES` | Retry attempts for failures | `3` |
| `DOWNLOAD_DIR` | PDF storage directory | `./data/pdfs` |
| `CACHE_DIR` | CSV cache directory | `./data/cache` |

## Compliance & Best Practices

### SEDAR+ Terms Compliance
- **Rate Limiting**: 1 second delays between requests by default
- **Respectful Usage**: User-Agent identifies as educational research
- **Caching**: Avoid repeat requests for same data
- **Attribution**: Clear source attribution in any derived works

### Data Quality
- **Error Handling**: Failed downloads logged but don't stop processing
- **Validation**: Basic data validation on CSV parsing
- **Versioning**: Tracks document versions and amendments
- **Audit Trail**: Complete logging of all collection activities

### Security
- **Environment Variables**: Sensitive config in .env files
- **No Hardcoded Secrets**: Database credentials externalized
- **HTTPS Only**: All requests use secure connections
- **Input Validation**: SQL injection prevention in database operations

## Monitoring & Debugging

### Logs
All activities logged to:
- Console output (INFO level)
- `sedar_collector.log` file (detailed logging)

### Results Tracking
Each run produces a JSON results file with:
- Processing statistics
- Error counts and details
- Timing information
- Data quality metrics

### Common Issues

**Rate Limiting Errors**: Increase `RATE_LIMIT_DELAY`
```bash
export RATE_LIMIT_DELAY=2.0
```

**Database Connection Issues**: Check Supabase credentials
```bash
# Test connection
python -c "from supabase import create_client; print('OK')"
```

**Large File Downloads**: Monitor disk space in `DOWNLOAD_DIR`

## Extending the System

### Adding NLP Processing
```python
# Future: Add sentiment analysis
def process_document_text(pdf_path):
    # Extract text from PDF
    # Run FinBERT sentiment analysis
    # Store results in mart_sentiment table
    pass
```

### Adding SEDI Integration
```python
# Future: Insider trading data
def fetch_sedi_data(issuer_no):
    # Scrape SEDI website
    # Parse insider transactions
    # Store in fact_insider_tx table
    pass
```

### Scheduling with Airflow
```python
# Future: Production scheduling
from airflow import DAG
from datetime import datetime, timedelta

dag = DAG(
    'sedar_daily_collection',
    schedule_interval=timedelta(hours=6),
    start_date=datetime(2024, 1, 1)
)
```

## Performance Considerations

- **Disk Space**: PDFs can be large (plan for 10GB+ for full collection)
- **Network**: Respectful rate limiting means collection takes time
- **Database**: Index properly for query performance
- **Memory**: Pandas DataFrames loaded in memory during processing

## Next Steps

1. **Test the basic collection** with a small date range
2. **Set up your database** using the provided schema
3. **Configure scheduling** for daily incremental updates
4. **Add PDF text extraction** for NLP processing
5. **Build web interface** for data access and visualization

## Support & Contributing

This system follows the architectural blueprint for a Canadian financial data platform. It's designed to be the foundation for a Quiver Quantitative-style service focused on Canadian markets.

For questions about compliance or usage, refer to the SEDAR+ terms of service and consider reaching out to CSA for bulk data licensing if needed.

## License

This project is for educational and research purposes. Ensure compliance with SEDAR+ terms of use and relevant data protection regulations.