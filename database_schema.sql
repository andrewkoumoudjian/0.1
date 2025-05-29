-- SEDAR+ Database Schema
-- =====================
-- 
-- This file contains the database schema for storing SEDAR+ data
-- Following the canonical schema outlined in the technical blueprint

-- Issuers dimension table
COMMENT ON TABLE public.dim_issuer IS 'Dimension table containing all reporting issuers from SEDAR+. Includes company profile information.';
CREATE TABLE IF NOT EXISTS public.dim_issuer (
    issuer_no TEXT PRIMARY KEY, -- Unique identifier for the issuer, sourced from SEDAR+
    name TEXT NOT NULL, -- Official name of the issuer
    jurisdiction TEXT, -- Principal jurisdiction of the issuer
    issuer_type TEXT, -- Type of issuer (e.g., Corporation, Trust)
    in_default BOOLEAN DEFAULT FALSE, -- Flag indicating if the issuer is in default
    active_cto BOOLEAN DEFAULT FALSE, -- Flag indicating if there is an active Cease Trade Order against the issuer
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Timestamp of when this issuer was first recorded in our system
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Timestamp of when this issuer was last observed or updated
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- Timestamp of the last update to this issuer's record
);

-- Document types dimension table
COMMENT ON TABLE public.dim_document_type IS 'Dimension table for classifying document types, categories, and access levels based on the SEDAR+ Filing Inventory.';
CREATE TABLE IF NOT EXISTS public.dim_document_type (
    document_type_id SERIAL PRIMARY KEY, -- Surrogate primary key for the document type
    filing_category TEXT, -- Broad category of the filing (e.g., "Continuous Disclosure", "Prospectus")
    filing_type TEXT, -- Specific type of filing (e.g., "Annual Financial Statements", "Management Information Circular")
    document_type TEXT, -- Granular type of the document (e.g., "Interim financial statements", "MD&A")
    access_level TEXT, -- Access level of the document (e.g., "Public", "Confidential")
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Timestamp of the last update to this record
    CONSTRAINT uq_document_type_natural_key UNIQUE (filing_category, filing_type, document_type) -- Natural key constraint
);

-- Main filings fact table
COMMENT ON TABLE public.fact_filing IS 'Fact table containing metadata for each filing submitted to SEDAR+. Each record represents a unique document.';
CREATE TABLE IF NOT EXISTS public.fact_filing (
    filing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Unique identifier for the filing record (surrogate key)
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no), -- Foreign key to the issuer who made the filing
    document_guid TEXT UNIQUE NOT NULL, -- Globally unique identifier for the document, sourced from SEDAR+
    filing_type TEXT, -- Type of filing (links conceptually to dim_document_type)
    document_type TEXT, -- Type of document (links conceptually to dim_document_type)
    submitted_date DATE, -- Date the filing was submitted to SEDAR+
    url TEXT, -- URL to download the actual document from SEDAR+
    size_bytes BIGINT, -- Size of the document in bytes
    version INTEGER DEFAULT 1, -- Version number of the document, if applicable
    superseded_by UUID REFERENCES public.fact_filing(filing_id), -- If this document version is superseded, points to the new version's filing_id
    status TEXT DEFAULT 'active', -- Status of the filing (e.g., active, amended, superseded)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Timestamp of when this filing record was created in our system
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- Timestamp of the last update to this filing record
);

-- Financial statement line items (for future use)
COMMENT ON TABLE public.fact_statement_line IS 'Stores extracted line items from financial statements (e.g., Revenue, Net Income). For future analytical use.';
CREATE TABLE IF NOT EXISTS public.fact_statement_line (
    id SERIAL PRIMARY KEY,
    filing_id UUID REFERENCES public.fact_filing(filing_id),
    fiscal_period TEXT,
    statement_type TEXT, -- 'income_statement', 'balance_sheet', 'cash_flow'
    line_item TEXT,
    value DECIMAL(20,2),
    currency TEXT DEFAULT 'CAD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insider trading data (from SEDI integration)
COMMENT ON TABLE public.fact_insider_tx IS 'Stores insider trading transactions, potentially integrated from SEDI data.';
CREATE TABLE IF NOT EXISTS public.fact_insider_tx (
    id SERIAL PRIMARY KEY,
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    insider_name TEXT,
    insider_role TEXT,
    trade_date DATE,
    transaction_type TEXT, -- 'buy', 'sell', 'option_exercise', etc.
    security_type TEXT,
    volume BIGINT,
    price DECIMAL(10,4),
    total_value DECIMAL(20,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sentiment analysis results
COMMENT ON TABLE public.mart_sentiment IS 'Stores results of NLP sentiment analysis performed on filing documents.';
CREATE TABLE IF NOT EXISTS public.mart_sentiment (
    id SERIAL PRIMARY KEY,
    filing_id UUID REFERENCES public.fact_filing(filing_id),
    overall_score DECIMAL(5,4), -- -1.0 to 1.0
    positivity DECIMAL(5,4),
    negativity DECIMAL(5,4),
    uncertainty DECIMAL(5,4),
    key_topics JSONB,
    model_version TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Financial ratios and metrics
COMMENT ON TABLE public.mart_financial_ratios IS 'Stores calculated financial ratios and metrics for issuers.';
CREATE TABLE IF NOT EXISTS public.mart_financial_ratios (
    id SERIAL PRIMARY KEY,
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    fiscal_period TEXT,
    ratio_name TEXT,
    ratio_value DECIMAL(10,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(issuer_no, fiscal_period, ratio_name)
);

-- User alerts and watchlists (for future web platform)
COMMENT ON TABLE public.user_alerts IS 'Supports user-defined alerts and watchlists for a potential web application.';
CREATE TABLE IF NOT EXISTS public.user_alerts (
    id SERIAL PRIMARY KEY,
    user_id UUID, -- Will reference user management system
    alert_type TEXT, -- 'new_filing', 'insider_trade', 'sentiment_change'
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    conditions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Collection job tracking
COMMENT ON TABLE public.collection_jobs IS 'Tracks the execution, status, and metadata of data collection jobs.';
CREATE TABLE IF NOT EXISTS public.collection_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT, -- 'incremental', 'backfill', 'manual'
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    status TEXT, -- 'running', 'completed', 'failed'
    records_processed INTEGER DEFAULT 0,
    errors JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fact_filing_issuer_no ON public.fact_filing(issuer_no);
CREATE INDEX IF NOT EXISTS idx_fact_filing_submitted_date ON public.fact_filing(submitted_date);
CREATE INDEX IF NOT EXISTS idx_fact_filing_filing_type ON public.fact_filing(filing_type);
CREATE INDEX IF NOT EXISTS idx_fact_filing_document_type ON public.fact_filing(document_type);
CREATE INDEX IF NOT EXISTS idx_fact_insider_tx_issuer_no ON public.fact_insider_tx(issuer_no);
CREATE INDEX IF NOT EXISTS idx_fact_insider_tx_trade_date ON public.fact_insider_tx(trade_date);
CREATE INDEX IF NOT EXISTS idx_mart_sentiment_filing_id ON public.mart_sentiment(filing_id);

-- Row Level Security (RLS) setup for multi-tenant access (optional)
-- ALTER TABLE public.fact_filing ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Users can only see their accessible data" ON public.fact_filing FOR SELECT USING (true); -- Modify based on your access requirements

-- Comments for documentation (table-level comments are now above each table)

-- Example queries for testing the schema:
/*
-- Get all filings for a specific issuer
SELECT f.*, i.name 
FROM fact_filing f 
JOIN dim_issuer i ON f.issuer_no = i.issuer_no 
WHERE i.name ILIKE '%shopify%' 
ORDER BY f.submitted_date DESC;

-- Get recent insider trading activity
SELECT i.name, it.insider_name, it.transaction_type, it.volume, it.price, it.trade_date
FROM fact_insider_tx it
JOIN dim_issuer i ON it.issuer_no = i.issuer_no
WHERE it.trade_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY it.trade_date DESC;

-- Get sentiment trends for a company
SELECT f.submitted_date, s.overall_score, f.filing_type
FROM mart_sentiment s
JOIN fact_filing f ON s.filing_id = f.filing_id
JOIN dim_issuer i ON f.issuer_no = i.issuer_no
WHERE i.name ILIKE '%shopify%'
ORDER BY f.submitted_date DESC;
*/