-- SEDAR+ Database Schema
-- =====================
-- 
-- This file contains the database schema for storing SEDAR+ data
-- Following the canonical schema outlined in the technical blueprint

-- Issuers dimension table
CREATE TABLE IF NOT EXISTS public.dim_issuer (
    issuer_no TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    jurisdiction TEXT,
    issuer_type TEXT,
    in_default BOOLEAN DEFAULT FALSE,
    active_cto BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document types dimension
CREATE TABLE IF NOT EXISTS public.dim_document_type (
    id SERIAL PRIMARY KEY,
    filing_category TEXT,
    filing_type TEXT,
    document_type TEXT,
    access_level TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main filings fact table
CREATE TABLE IF NOT EXISTS public.fact_filing (
    filing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    document_guid TEXT UNIQUE NOT NULL,
    filing_type TEXT,
    document_type TEXT,
    submitted_date DATE,
    url TEXT,
    size_bytes BIGINT,
    version INTEGER DEFAULT 1,
    superseded_by UUID REFERENCES public.fact_filing(filing_id),
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial statement line items (for future use)
CREATE TABLE IF NOT EXISTS public.fact_statement_line (
    id SERIAL PRIMARY KEY,
    filing_id UUID REFERENCES public.fact_filing(filing_id),
    fiscal_period TEXT,
    statement_type TEXT, -- 'income_statement', 'balance_sheet', 'cash_flow'
    line_item TEXT,
    value DECIMAL(20,2),
    currency TEXT DEFAULT 'CAD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insider trading data (from SEDI integration)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sentiment analysis results
CREATE TABLE IF NOT EXISTS public.mart_sentiment (
    id SERIAL PRIMARY KEY,
    filing_id UUID REFERENCES public.fact_filing(filing_id),
    overall_score DECIMAL(5,4), -- -1.0 to 1.0
    positivity DECIMAL(5,4),
    negativity DECIMAL(5,4),
    uncertainty DECIMAL(5,4),
    key_topics JSONB,
    model_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial ratios and metrics
CREATE TABLE IF NOT EXISTS public.mart_financial_ratios (
    id SERIAL PRIMARY KEY,
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    fiscal_period TEXT,
    ratio_name TEXT,
    ratio_value DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issuer_no, fiscal_period, ratio_name)
);

-- User alerts and watchlists (for future web platform)
CREATE TABLE IF NOT EXISTS public.user_alerts (
    id SERIAL PRIMARY KEY,
    user_id UUID, -- Will reference user management system
    alert_type TEXT, -- 'new_filing', 'insider_trade', 'sentiment_change'
    issuer_no TEXT REFERENCES public.dim_issuer(issuer_no),
    conditions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Collection job tracking
CREATE TABLE IF NOT EXISTS public.collection_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT, -- 'incremental', 'backfill', 'manual'
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT, -- 'running', 'completed', 'failed'
    records_processed INTEGER DEFAULT 0,
    errors JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- Comments for documentation
COMMENT ON TABLE public.dim_issuer IS 'Dimension table containing all reporting issuers from SEDAR+';
COMMENT ON TABLE public.fact_filing IS 'Fact table containing all filings metadata from SEDAR+';
COMMENT ON TABLE public.fact_statement_line IS 'Financial statement line items extracted from filings';
COMMENT ON TABLE public.fact_insider_tx IS 'Insider trading transactions from SEDI';
COMMENT ON TABLE public.mart_sentiment IS 'NLP sentiment analysis results for filings';
COMMENT ON TABLE public.mart_financial_ratios IS 'Calculated financial ratios and metrics';

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