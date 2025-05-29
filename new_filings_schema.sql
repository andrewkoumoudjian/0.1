CREATE TABLE IF NOT EXISTS filings (
  filing_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  issuer_no    TEXT NOT NULL,
  document_guid TEXT UNIQUE NOT NULL,
  date_filed   DATE NOT NULL,
  filing_type  TEXT,
  document_type TEXT,
  size_bytes   BIGINT,
  pdf_data     BYTEA       -- stores the raw PDF
);
