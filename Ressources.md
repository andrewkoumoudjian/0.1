Building a Canadian Financial Data Platform with SEDAR+ Data

Introduction: This guide outlines the technical and architectural blueprint for a web platform similar to Quiver Quantitative, focused on Canadian markets and powered by SEDAR+ data. We will cover data ingestion of all publicly available SEDAR+ filings (financial statements, insider trading reports, press releases, MD&As, prospectuses, etc.), the design of a fast-queryable data store, data enrichment techniques (e.g. financial ratios, NLP-based sentiment), and delivery via a modern web application with dashboards, search, and alerts. We also discuss a freemium model (free raw data vs. premium analytics), recommend technologies (from ETL pipelines to charting libraries), and address data update workflows and compliance. Throughout, we emphasize using robust, scalable solutions and official data sources.

Overview of SEDAR+ and Data Sources

SEDAR+ (System for Electronic Document Analysis and Retrieval Plus) is the Canadian electronic filing system for securities disclosure, analogous to the SEC’s EDGAR system in the U.S. It is a centralized web platform used by public companies, investment funds, and other market participants to file and disclose information in Canada’s capital markets ￼ ￼. SEDAR+ consolidates what was previously multiple systems, streamlining compliance and data access for regulators and investors ￼. All documents required by Canadian securities regulators are transmitted through SEDAR+ under new regulations (NI 13-103) ￼.

Types of data available: SEDAR+ contains a wide range of filings and disclosures from Canadian companies and funds. Key examples include:
	•	Financial statements and reports: Annual reports, quarterly financial statements, and Management’s Discussion & Analysis (MD&A) documents, which give insight into a company’s financial performance and management’s perspective ￼.
	•	Prospectuses and offering documents: Filings for IPOs or other securities offerings, which include detailed business descriptions and financial statements ￼.
	•	Insider trading reports: Disclosures of trades by insiders (officers, directors, significant shareholders), typically filed via the separate SEDI system, but also aggregated in SEDAR-related datasets ￼. These indicate when insiders buy or sell shares, which can signal confidence or concern.
	•	Press releases and material change reports: Press releases filed to meet regulatory requirements (material news), and material change reports that detail significant company events.
	•	Other regulatory filings: Annual information forms, proxy circulars, technical reports (e.g. NI 43-101 for mining companies ￼), exemption applications, cease trade orders, and more.

SEDAR+ is intended to provide public access to all these disclosure documents. Investors can search and download documents through the SEDAR+ web interface ￼. In building our platform, we will ingest this rich dataset of filings and transform it into structured, queryable information.

Note on insider data: Currently, insider trading reports in Canada are filed on SEDI (System for Electronic Disclosure by Insiders) ￼. Phase 1 of SEDAR+ replaced the old SEDAR filings system ￼, but did not yet subsume SEDI. To include insider trading data, our platform will integrate SEDI disclosures as well. This may involve scraping the SEDI site or using third-party data providers. For example, QuoteMedia provides aggregated SEDAR filings and insider trading data via API ￼. We can leverage such APIs or build scrapers for SEDI to ensure insider trades are part of the dataset.

Regulatory compliance: All data we use is publicly available regulatory disclosure. SEDAR filings are meant for investor access ￼, and reusing them in our platform is generally permissible. However, we must adhere to any usage policies (e.g. not misrepresent data, properly attribute sources if required, and include disclaimers that our platform is not an official source). We’ll ensure personal information (like insider names) is handled in line with privacy laws, though these are public disclosures. We will also include standard disclaimers (e.g. “Not investment advice” for any analytics we provide).

Data Ingestion Architecture

Ingesting SEDAR+ data at scale is a core challenge. The platform should automatically fetch new filings across all companies and document types, parse them, and store them for analysis. We propose a robust ETL (Extract-Transform-Load) pipeline that operates continuously or on a schedule to keep the data up-to-date.
	•	Extraction (Data Ingestion): We will build connectors to retrieve documents from SEDAR+. If SEDAR+ offers an official feed or API for public disclosures, we will use that. (As of now, SEDAR+ primarily has a web portal; data providers like FactSet/QuoteMedia aggregate this data via their APIs ￼, which could be a faster route to access filings). In absence of a direct API, we can implement web scrapers to crawl the SEDAR+ search pages for new filings. This may involve handling login or CAPTCHA if required (the legacy SEDAR had CAPTCHA, which some scrapers bypassed with OCR ￼). We should design the scraper to iterate through new filings by date or to monitor company profiles for updates. Each fetched document (often PDF, HTML, or text) will be saved to a raw storage location (e.g. an Amazon S3 bucket or other cloud storage). We also extract metadata such as company name, filing type, date, and filing description. This metadata can often be parsed from the SEDAR+ search results or the document headers.
	•	Transformation (Parsing and Processing): Once a filing is fetched, we transform it into structured or searchable data:
	•	Text extraction: Many filings are PDFs. We will use PDF parsing libraries or OCR (if PDFs are scanned images) to extract text content from financial statements, MD&As, press releases, etc. The extracted text will be cleaned (removing page headers/footers, fixing encoding issues) and stored for indexing and NLP analysis.
	•	Structured data extraction: Certain documents, like financial statements, contain structured numerical data (balance sheets, income statements, etc.). If filings are available in XBRL (a financial data XML format) – note: Canada allows voluntary XBRL filings ￼ ￼ – we will parse those for high-quality structured data. If not, we might implement heuristic parsers to read tables from the statements (using libraries like Pandas for PDF table extraction or an OCR for tables). Key financial line items (revenue, net income, assets, etc.) can be mapped into a database schema. Insider trading reports will be parsed for details like insider name, relationship, date of trade, security, volume, and price.
	•	Normalization: We standardize entity names (e.g., ensure company names or tickers match across all data types), convert financial amounts to consistent units, and classify documents by type. We also timestamp each record.
	•	Enrichment calculations: As part of transformation, we might immediately calculate some basic analytics – for example, computing financial ratios from a financial statement (gross margin, EPS, debt-to-equity, etc.) and tagging sentiment scores on text (see more in the analytics section below). This can be done in the transformation stage so that the enriched data is ready for querying.
	•	Loading: Finally, the cleaned and structured data is loaded into our databases/storage (detailed in the next section). For example, after parsing an annual report, we insert the financial figures into a Financials table, the text into a search index, and the raw PDF into cloud storage with a reference in a Filings table.
	•	Scheduling and Orchestration: To handle this pipeline reliably, we can use an orchestration tool. Apache Airflow is a popular choice for scheduling ETL jobs (e.g., a DAG that runs nightly to fetch new filings) and handling dependencies. Alternatively, cloud-managed services like AWS Step Functions or Google Cloud Composer can coordinate scraping, parsing, and loading steps. The pipeline could run in batch (e.g., every hour check for new filings) and also be triggered ad-hoc (e.g., if a user requests an on-demand update for a specific company).
	•	Scalability considerations: Ingesting thousands of documents (especially PDFs) can be time-consuming. We should parallelize where possible. For example, use a queue of URLs to fetch, processed by multiple workers (instances or containers) in parallel. Cloud services (AWS Lambda or AWS Fargate) could help scale out the scraping tasks serverlessly. We will also implement error handling and retries (e.g., network failures, or skip a file if it’s causing parse errors and log it for review). Using a message queue (like AWS SQS or Apache Kafka) can decouple the scraping from processing: one component grabs raw files and pushes messages with file info, another component picks up messages to parse and load into DB. This improves resilience and allows scaling each part independently.

Pipeline architecture: It’s useful to conceptualize our data pipeline in layers. A modern data ingestion architecture often consists of six layers: 1) Ingestion, 2) Collection, 3) Processing, 4) Storage, 5) Querying, 6) Visualization ￼. In our case:
	•	Ingestion – scraping or API retrieval from SEDAR+/SEDI (as described above).
	•	Collection – temporarily staging raw files (e.g., on S3 or a file system) and metadata.
	•	Processing – parsing files, running NLP, computing metrics (the ETL transformation steps).
	•	Storage – saving the processed data into databases/data lakes (detailed next).
	•	Querying – enabling fast queries via databases or search indexes (for both our backend and user-facing features).
	•	Visualization – presenting data on the web platform, dashboards, charts, etc.

Example of a modern data pipeline architecture (using AWS services) from data ingestion on the left, through storage/processing in the middle, to consumption on the right. In this design, raw data is ingested into a “data lake” (object storage), ETL jobs validate and transform it into refined datasets (e.g., Parquet files or database tables), which are then loaded into analytic databases and search indexes for use in dashboards, machine learning (SageMaker), and interactive queries (Athena/Redshift). Our platform’s pipeline will follow similar principles of staging raw data, processing it, and curating data for fast access. ￼ ￼

Data Storage and Database Schema

Proper data storage design is crucial for supporting fast queries and analytics. We will employ a combination of storage solutions, each optimized for different query types:
	•	Data Lake for raw and semi-structured data: All raw filings (PDFs, HTML, etc.) will be stored in a scalable object store (such as Amazon S3, Google Cloud Storage, or Azure Blob Storage). This serves as our archive of source documents (sometimes called the “bronze” layer in a medallion architecture) ￼ ￼. In addition, any intermediate or partially processed data (like extracted text or XBRL XML files) can be stored here. Using a data lake ensures we have the original data for reference and can re-process if needed, and it can hold large volumes of files cheaply.
	•	Relational database for structured data: A SQL database will store structured information that benefits from relational queries. We propose using a PostgreSQL or MySQL database (or a cloud equivalent like Amazon RDS, Cloud SQL, or Azure SQL) for core structured data (the “silver/gold” refined layers). The schema might look like:
	•	Companies table: Contains company profiles – company_id (primary key), company name, ticker symbol, industry/sector classification, etc. This allows joining filings to specific companies and filtering by sector.
	•	Filings table: Each filing/document is a record – filing_id, company_id (FK to Companies), date, filing_type (e.g. Annual Report, MD&A, Press Release, Insider Report, etc.), title/description, and a reference (URL or path) to the document in the data lake or text index. We may also store a short summary or key points for quick reference.
	•	Financials table: Stores numeric financial data by company and period. For example, fields for fiscal period (year/quarter), and various metrics: revenue, net_income, assets, liabilities, EPS, etc. This can be normalized into multiple tables (e.g., an IncomeStatement table, BalanceSheet table, etc., or a key-value structure for flexibility). Primary key could be (company_id, fiscal_period, statement_type, line_item) for a very normalized design, or simply one table per statement type. Having this structured financial data allows computing ratios and comparisons easily with SQL.
	•	InsiderTrades table: Each record could include company_id, insider_name, insider_position (e.g. CEO, Director), date of trade, trade_type (buy or sell), security (e.g. common shares), volume, price, and any remarks. This allows querying trends like “total insider buys of Company X in last 6 months”.
	•	Analytics tables: We might also create tables for derived analytics: e.g., FinancialRatios (company_id, period, ratio_name, value) to store precomputed ratios; SentimentScores (company_id, filing_id, sentiment_score, key_topics) for NLP outputs per document; or a Alerts table for user-defined alert triggers.
A relational DB is great for flexible queries and joins, such as “find all companies with revenue > X and insider buys last quarter” or “list filings of type prospectus in the last year”. We will index important columns (e.g., company_id, filing_type, date) to accelerate lookups.
	•	Search index for full-text search: To enable users to search the content of filings (e.g., search all MD&A texts for keywords like “bitcoin” or “supply chain”), we will use a search engine. Elasticsearch (OpenSearch) or Apache Solr are good choices. We will index the textual content of each document, along with metadata. The filing_id will link search results back to the relational data. The search index allows advanced text queries, filtering by company or date, and fast full-text retrieval. We can also incorporate semantic search capabilities (using embeddings) in the future, but initially keyword search with ranking is sufficient.
	•	Analytics database / data warehouse: For heavy analytical queries (especially across many companies or long time ranges), a specialized analytical data store can be used. Options include:
	•	A columnar data warehouse like Amazon Redshift, Google BigQuery, or Snowflake – these are optimized for aggregations on large datasets. We could periodically load our structured financial and trading data into such a warehouse for users to run custom queries or for powering dashboards that compare many companies.
	•	An OLAP engine or in-memory cube for quick multidimensional analysis (e.g., Apache Druid or ClickHouse). For instance, if we want to very quickly query “average sentiment of mining sector vs tech sector over 4 quarters” or “10-year trend of insider selling by sector”, an OLAP store could accelerate that.
	•	However, given the likely scale (Canadian market has a few thousand public companies), a well-indexed PostgreSQL might handle many queries. We can start with the relational DB for most needs and introduce a warehouse as we scale and add more historical data.
	•	Cache layer: To support a high-traffic web platform, we should add a caching layer for frequent queries. For example, an in-memory cache like Redis can store results of common queries or API responses (such as “latest filings for company X” or summary statistics for a sector) so that the web server can serve them quickly without hitting the DB every time. We will also use CDN caching for static content (and possibly for certain public data API endpoints if we provide those).

Database schema and design considerations: Our schema design aims to balance 3NF normalization with practicality. Highly normalized schemas (many tables) make updates and storage efficient, but joining many tables can slow read queries. We will likely denormalize some data for performance. For example, storing a company_ticker or company_name directly in the Filings table (in addition to the company_id) can make querying easier, at the expense of slight redundancy. Similarly, precomputing and storing aggregates (like trailing 12-month financial figures, or sector averages) can speed up dashboard queries. This is a form of caching at the data level.

Fast querying: To achieve fast query responses on the platform:
	•	We will write optimized SQL queries and use proper indexes. For textual search, the search engine will handle query performance.
	•	For analytical queries (like comparing many companies), we might utilize the data warehouse or pre-aggregate data. For example, nightly jobs could calculate sector-level metrics or top-10 lists and store them ready to serve.
	•	We may employ read replicas for the relational database to distribute load (most web queries will be reads).
	•	If using cloud databases, choosing an appropriate instance size or cluster and scaling as needed is important. Services like Aurora (on AWS) automatically scale and could be considered.

Storage infrastructure: We recommend a cloud-based infrastructure for scalability:
	•	Object storage: Amazon S3 is a reliable choice for the data lake (with lifecycle policies to move older data to cheaper storage if needed). S3 provides 11 9’s durability and integrates with other services easily.
	•	Database hosting: Use managed database services (Amazon RDS/Aurora, Google Cloud SQL, or Azure Database) for the relational data to offload maintenance. Ensure backups and point-in-time recovery are enabled, given the value of historical data we accumulate.
	•	Search: Use a managed Elasticsearch service (AWS OpenSearch Service or Elastic Cloud) for ease of maintenance and scaling.
	•	Warehouse: If we use one, BigQuery or Redshift can be considered (BigQuery is serverless and scales automatically, which is convenient; Redshift gives more control and can integrate with S3 via Redshift Spectrum as shown in the architecture diagram【47†】).

Finally, ensure security in storage: All sensitive data at rest should be encrypted (most cloud services do this by default). Although filings are public, user data (accounts, preferences) must be protected. We will enforce access controls so that, for example, only authorized users can access premium data tables or download bulk data (preventing scrapers from easily stealing our aggregated data).

Data Enrichment and Analytics Features

One of the key value propositions of our platform (beyond raw data access) is data enrichment and analytics on top of the filings. Here we detail how the platform will derive insights like financial ratios, sentiment analysis, trends, and comparison tools.

Financial Calculations and Ratios

From the structured financial statement data, we will compute a range of financial ratios and metrics to help users analyze company performance. These calculations can be done during data ingestion (for standard metrics) and updated whenever new data arrives. Examples include:
	•	Profitability ratios: gross margin, net margin, return on equity (ROE), return on assets (ROA). For instance, after parsing an income statement and balance sheet, we can calculate ROE = Net Income / Shareholders’ Equity.
	•	Liquidity and leverage: current ratio, quick ratio, debt-to-equity. E.g., debt-to-equity = Total Debt / Equity (from balance sheet data).
	•	Growth metrics: year-over-year or quarter-over-quarter growth in revenue, earnings, etc. We can compute these by storing previous periods and calculating differences.
	•	Per-share values: earnings per share (EPS), if not directly given, from Net Income and shares outstanding.
	•	Valuation metrics (if we incorporate market data): while SEDAR+ data itself doesn’t provide stock prices, we might integrate price data through a public API or partnership. That would allow things like P/E ratio, price-to-book, etc., updated in real-time. (This is optional, but Quiver Quantitative often merges filing data with market data; for a comprehensive platform, we’d eventually include that.)

These derived metrics will be stored in our database (e.g., in a FinancialRatios table or added as columns in a financial summary table). This allows users (especially premium users) to quickly see, for example, a company’s profitability trend over 5 years, or to filter companies by certain financial criteria.

We can provide code snippets or pseudocode for how these metrics are calculated as part of documentation. For example, in Python pseudocode:

# Example: Calculate financial ratios for a company for a given period
for company_id, period in Financials:
    net_income = financials[company_id][period]['NetIncome']
    revenue = financials[company_id][period]['Revenue']
    equity = financials[company_id][period]['TotalEquity']
    debt = financials[company_id][period]['TotalDebt']
    
    ratios = {}
    ratios['NetMargin'] = net_income / revenue if revenue else None
    ratios['ROE'] = net_income / equity if equity else None
    ratios['DebtToEquity'] = debt / equity if equity else None
    # ... other ratios
    
    save_to_db(company_id, period, ratios)

These computations are straightforward, but the challenge is ensuring the raw data is accurate (e.g., handling if companies report in different accounting standards or currencies – since it’s Canadian, most in CAD, but some might be USD). We will standardize units and possibly note fiscal year differences.

NLP and Sentiment Analysis on Filings

Why NLP on filings? The textual portions of filings (like the MD&A, press releases, prospectus overviews) contain qualitative information that can be indicative of company outlook. As noted by legal analysts, “the MD&A portion of a filing is a ripe target for sentiment analysis because it is less structured” ￼— unlike financial statements full of numbers, MD&A is narrative, discussing management’s view on financial results, risks, and future plans. Markets can react to the tone and language in these sections ￼. Thus, our platform will use Natural Language Processing techniques to analyze these texts.

Sentiment Analysis: We will implement sentiment analysis to gauge whether a document’s tone is positive, negative, or neutral. There are a few approaches:
	•	Dictionary-based (lexicon) approaches like VADER (Valence Aware Dictionary for Sentiment Reasoning) or a finance-specific lexicon (e.g., Loughran-McDonald sentiment word lists which are tailored for financial context). These count positive vs negative words. For example, terms like “record profit” or “strong growth” vs “significant doubt” or “impairment” can affect sentiment scores.
	•	Machine Learning models: We can use pre-trained transformer models fine-tuned for finance. There are models like FinBERT (BERT model tuned on financial text) which output a sentiment score for a given text (positive, negative, neutral). We could also leverage cloud NLP APIs (Amazon Comprehend, Google Cloud NLP) which provide sentiment analysis, though a generic API might not understand finance context as well as FinBERT.
	•	Approach: Likely use a model like FinBERT or a similar Hugging Face Transformers model for finance. We would run each MD&A or press release through the model and get a sentiment polarity and score. We might also perform topic modeling or key phrase extraction to highlight what topics the filing discusses (e.g., “AI initiative”, “debt refinancing”, etc.), adding to the insights.

We’ll store sentiment results in the database. For example, a SentimentScores table might have columns for filing_id, overall_sentiment (e.g. +1 positive, -1 negative), and maybe subscores for sections or categories (maybe the model can give sentiment per sentence which we could aggregate by section). We can also present a sentiment trend: e.g., plot how the sentiment of a particular company’s quarterly MD&A has changed over time, or compare sentiment across companies in a sector.

Textual analytics beyond sentiment: We can incorporate other NLP-driven features:
	•	Word frequency/cloud: Highlight which keywords are mentioned frequently in a filing (e.g., if “cost” or “competition” or “lithium” appears many times, it indicates focus areas).
	•	Readability or tone metrics: Calculate something like a Fog Index or sentiment tone (are they using more optimistic language this quarter?).
	•	Anomaly detection in language: Using NLP to flag if a company’s filing language changes significantly from previous (there’s research showing such changes can precede issues).
	•	Summarization (AI-generated insights): A premium feature could be an AI-generated summary of a long filing. We could fine-tune a summarization model (or use an API like OpenAI GPT-4) to produce a concise summary of an annual report or press release, and highlight crucial points (“Management highlights record revenues but notes uncertainties in supply chain.”).

Such AI-generated summaries or highlights would be clearly labeled and behind the paywall (as they are value-added content).

Insider Trading Trends

Insider trading data (from SEDI) will be used to generate analytics like:
	•	Insider buy/sell summary: For each company, show how many shares insiders bought vs sold in a given period, and the net effect. Heavy insider buying might be a bullish signal, and heavy selling bearish (though there are caveats).
	•	Insider trading visualization: We can plot insider trades on a timeline (possibly alongside stock price if integrated). For example, a chart where each insider buy/sell is a point, showing clusters of insider buying before a stock’s rise.
	•	Ranking and alerts: Identify the companies with the most insider buying in the last month, or which sectors have insiders buying more than selling.
	•	We can also categorize insiders (e.g., officers vs independent directors) to see who is trading.

These analytics require aggregating the raw trade records. We will likely create summary views or cache results:
	•	e.g., a materialized view for “insider_net_activity” with columns (company_id, last_3_months_net_shares, last_3_months_num_trades, etc.).
	•	Possibly, compute insider sentiment score: +1 for buys, -1 for sells, weighted by size relative to their holdings, to quantify how positive insiders collectively are.

Comparison Tools Across Companies & Sectors

Users will want to compare companies or view sector-level analytics. Our data model and analytics enable several comparison features:
	•	Company comparison dashboard: The user selects multiple companies (or an entire industry) and chooses metrics to compare. For instance, compare revenue growth of Company A vs Company B over 5 years (rendered as a line chart), or compare their current valuation metrics and insider activity side by side. We will implement the backend such that one query can retrieve all needed data for selected companies (using SQL WHERE company_id IN (...) or similar). The front-end can then visualize it.
	•	Sector overviews: We will tag each company with a sector/industry. This allows aggregate computations. For example, we can show the average P/E in the Technology sector vs Financials, or total insider buying by sector. These could be shown in interactive charts (bar charts, etc.). We might precompute some sector aggregates (especially if using NAICS or GICS classifications for companies).
	•	Screeners and filters: A powerful feature (likely premium) is a screener where users filter companies by criteria: e.g., “show me companies in mining sector with positive MD&A sentiment and increasing insider buying and P/E < 15”. This essentially translates to queries across our different data sets. We will need to implement an efficient way to handle these queries (possibly pre-index some fields or use the data warehouse). A user-friendly UI can be provided to build these filters without writing code.

Analytics Delivery

The results of these enrichments will be delivered in various forms on the platform:
	•	Numeric metrics (ratios, growth rates) will be displayed in tables or charts.
	•	Sentiment analysis might be shown as colored indicators (e.g., a positive sentiment might show a green upward arrow icon next to the filing, negative a red arrow) along with a tooltip or link to a detailed sentiment report.
	•	Trend charts: we will have time-series charts for financial performance and sentiment trends.
	•	Peer comparisons: maybe a spider/radar chart for multi-metric comparison between a company and its peers.
	•	Downloadable data: users (especially premium) might download a CSV of a company’s last 5 years of financials or a list of insider trades, to do their own analysis.

By enriching raw data into these insights, we significantly increase the platform’s value beyond what a user could get by manually reading SEDAR filings. It’s worth noting, however, that data quality is paramount – we need to validate these analytics. For example, double-check calculations for anomalies (like extremely high ratios might indicate a parsing issue or an outlier we need to handle). We should implement some validation rules during ETL (e.g., if a parsed balance sheet doesn’t balance assets vs liabilities+equity, flag it).

Platform Architecture and Technology Stack

Now we turn to how the platform will deliver this data to end users. We envision a modern web application that is responsive (usable on desktop or mobile) and provides interactive features. The architecture will likely follow a standard web-app model with a client-facing front end, a server-side backend (with REST/GraphQL APIs), and connections to the databases described.

Front-End (Client Side)

Web UI: We will build a single-page application (SPA) for a dynamic, responsive user experience. Likely we will use React (with TypeScript) due to its popularity and rich ecosystem, or an equivalent framework like Vue.js or Angular. React paired with a UI component library (e.g., Material-UI or Ant Design) can accelerate development of a professional-looking interface. Key aspects:
	•	The UI will have dashboards, charts, tables, and forms (for search and alerts). We’ll ensure responsive design (using CSS frameworks or flexbox/grid) so that it works on various screen sizes.
	•	Routes in the SPA might include: Home (overview), Company page (detailed view with that company’s filings and analytics), Sector page (aggregated stats), Insiders (maybe a dashboard focusing on insider trades), Search results, User account settings, etc.
	•	We will implement client-side state management (Redux or context API in React) to manage things like user login state, watchlists, etc., for a smooth user experience.

Interactive charts: For charting and visualizations, we can use JavaScript libraries:
	•	D3.js is extremely powerful for custom visualizations. It gives low-level control to create interactive SVG charts. We might use D3 for any bespoke visualization needs (e.g., a custom insider trading timeline chart).
	•	Charting libraries like Chart.js, ECharts, or Highcharts can produce common chart types with less effort. For time-series, bar charts, pie charts, these libraries are convenient. For example, Chart.js allows creating line charts for financial metrics easily, and ECharts has good support for interactive features like tooltips, zooming, etc.
	•	Plotly is another option (especially if we consider embedding some Python-generated charts via Plotly Dash), but staying in the JS world might be simpler for a SPA.
	•	Considering we might have a lot of data points (e.g., 10-year daily insider trades), the library should handle performance – many libraries can plot thousands of points, but for very large data we may pre-aggregate or sample the data.
	•	We should ensure accessibility (colors, etc.) and possibly have light/dark mode for the charts.

Responsive and mobile: Many investors may check data on their phone, so we ensure the layout collapses nicely into a single-column mobile view, charts are scrollable or simplified for mobile, etc. We might develop a companion mobile app in the future, but initially a PWA (progressive web app) could suffice.

Back-End (Server Side & API)

The backend will handle requests from the front-end, perform business logic, and query the databases. We have options for the back-end stack:
	•	Language: Common choices are Node.js (JavaScript/TypeScript) or Python or Java/C#.
	•	Node.js/TypeScript might be a good fit if our front-end team is also using TypeScript – code sharing and consistency. Node is event-driven and can handle many I/O operations efficiently (good for an API server making DB queries).
	•	Python (with frameworks like Flask/FastAPI or Django) is great especially if we already use Python for data processing. It has rich scientific libraries which might let us reuse some code for analytics on the fly. FastAPI, for instance, can build high-performance APIs and is easy to write.
	•	We could even split: use Python for data pipeline and heavy analytics jobs, and Node.js for the web API for efficiency. However, using one language across might simplify hiring and code maintenance.
	•	Framework: If Node, something like Express or NestJS (which is TypeScript and structured) for building the REST API. If Python, FastAPI or Flask for quick development, or Django if we want an all-in-one with ORM (though our needs might not require a full Django overhead).
	•	API design: likely RESTful endpoints for each resource (e.g., /api/companies/{id}/filings, /api/search?query=x, /api/analytics/insiders?company=y). Alternatively, a GraphQL API could allow the client to request exactly the data it needs (this can be efficient for a rich data schema and is quite developer-friendly for front-end). GraphQL would fit well with a React/Apollo Client front-end for example. However, REST is simpler to implement and cache. We may choose based on team expertise.
	•	The API will include authentication endpoints for login/registration, since we have user accounts (for saving preferences, setting alerts, and differentiating free vs premium access).
	•	We will implement role-based access control (free vs premium user roles). For example, certain API endpoints (or certain fields in responses) will check the user’s subscription status. E.g., a free user hitting /api/analytics/insider-trends might get a basic summary, whereas a premium user gets detailed data.

Performance & Scalability: The backend should be stateless (so we can run multiple instances behind a load balancer). We’ll containerize the application (Docker) and possibly orchestrate with Kubernetes or use cloud auto-scaling services. For example, on AWS we could deploy the Node/Python API on ECS or as serverless AWS Lambda functions behind an API Gateway (serverless can scale and we pay per request). However, for real-time streaming (like if we ever provide live updates or websockets for alerts), a persistent server process might be easier. A middle ground is AWS Fargate or Azure Container Instances for containers without managing servers. In any case, horizontal scaling is key: as user load increases, we spin up more instances of the web server.

Integration with database: The server will query our databases. Using an ORM (Object-Relational Mapping) like SQLAlchemy for Python or TypeORM for Node can speed development, but for performance we might write raw SQL for complex queries. We must also be careful to avoid N+1 query problems by doing proper JOINs or using the database to do heavy lifting (databases are optimized in C, better than looping in Python for large sets). For search, the backend will query Elasticsearch (likely via its REST API or a client library) when the user uses the search bar.

Security: We will use HTTPS for all client-server communication (TLS certificates via Let’s Encrypt or cloud LB). Implement proper authentication (probably JWT tokens for API auth, or session cookies if using a traditional web server). We’ll store passwords hashed (if not using a third-party identity provider). Protect against common web vulnerabilities (use frameworks to avoid SQL injection, validate inputs, rate-limit certain endpoints to prevent abuse of free data scraping, etc.).

Data Delivery: Downloads, Dashboards, Search, Alerts

We have several modes of delivering information to users, each with its backend support:
	•	Raw Data Downloads: We will provide a section (or specific buttons on pages) for downloading datasets. For example, on a company page, a user can click “Download financials (CSV)” to get a spreadsheet of that company’s financial statements. We’ll generate these on-demand by querying the database and formatting CSV/Excel, or pre-generate for popular companies periodically. We might also allow a full dataset download (like “all filings metadata in last year”) for researchers – likely behind the paywall due to the volume. If demand for bulk data is high, we could even offer a direct data dump or an API key for programmatic access (this could be a B2B offering).
	•	Interactive Dashboards: Some analytics may be complex enough that pre-building a dashboard interface is beneficial. We can create interactive pages where users can toggle options and see charts. For example, an “Insider Trading Dashboard” where one can filter by sector and date range and the charts update (using front-end code to fetch data via API calls dynamically). We might integrate an existing BI tool for heavy analysis (like an embedded Apache Superset or Metabase for internal use or power users), but likely we’ll create custom pages for a seamless UI. The key is our backend provides endpoints that return the needed aggregated data in JSON for the front-end to render.
	•	Search Functionality: The platform will have a search bar allowing users to search across filings and companies. We will implement this by leveraging the search index (Elasticsearch). The backend will take the query, perhaps enhance it (we can add wildcards or handle typos using Elasticsearch’s capabilities), and filter results. Users can also use advanced filters (e.g., restrict by document type or date). We’ll also support searching for companies by name or ticker (that can be a separate quick lookup query to the Companies table or an indexed search field). Search results page will show matches (with snippet of text highlighting the query terms, which Elasticsearch can provide).
	•	Alerts System: A premium feature will be user-defined alerts. Users can subscribe to events like “new filing by Company X” or conditions like “insider buy > 10k shares in any my watchlist company” or “when Company Y’s sentiment score drops below 0”. Implementing alerts involves:
	•	A table or service to store subscriptions (user, alert type, parameters).
	•	A background monitoring job that runs periodically (or in real-time via triggers) to check conditions. For example, after ingesting new data, the system can check “does this new filing match any user’s alert criteria?”.
	•	If an alert condition is met, the system sends a notification. Initially, email alerts are simplest (we integrate with an email service, e.g., AWS SES or SendGrid). Push notifications or SMS could be added later (if we make a mobile app or use web push).
	•	Users manage their alerts through the UI (creating, editing, deleting subscriptions). The backend provides endpoints to handle this securely (ensuring users can only affect their own alerts, etc.).
	•	AI Assistant (future idea): As a premium offering, we could include an AI chatbot or Q&A system that allows users to ask questions about the filings (“What were the main risk factors mentioned by Company X last year?”) which would use our data and an NLP model to answer. This would involve an advanced use of our data and possibly large language models. While not in initial scope, our architecture (with all data digitized and indexed) would enable this later.

Tech Stack Summary

Bringing it all together, here are technology recommendations for each component of the system:
	•	Infrastructure / Hosting: Use cloud providers for reliability and scalability. For example, AWS can cover all needs: EC2/ECS for hosting the web app, S3 for storage, RDS for database, OpenSearch for search, Lambda/Batch for ETL jobs, CloudWatch for monitoring, etc. GCP or Azure have equivalents (Google Cloud Storage, Cloud SQL, etc.). A containerized deployment on Kubernetes (Amazon EKS, Google GKE, or Azure AKS) would give flexibility and cloud-agnostic possibilities, but managed services can reduce ops work initially.
	•	ETL Pipeline: Python is ideal for writing the ingestion and parsing scripts due to rich libraries (requests/BeautifulSoup for web, PyPDF2/Tika for PDF, pandas for data manipulation, etc.). Schedule via Airflow (which can itself be hosted on AWS MWAA or GCP Cloud Composer to avoid managing servers) or use cloud-native (AWS Glue for data cataloging, Step Functions for orchestration as in the AWS reference architecture ￼). For parsing tasks that can be parallelized, consider AWS Batch or Google Cloud Functions for serverless scaling. Ensure the pipeline code is modular and well-logged (so we can track which filings were processed, and handle failures gracefully).
	•	Databases: For relational, use PostgreSQL (for its robustness and features like JSONB which can store semi-structured data if needed). Use a managed service (e.g., Amazon Aurora Postgres for high performance and automatic replication). For analytics, consider BigQuery for its ease with large data and no-index requirement, or Redshift if sticking to AWS (note Redshift Spectrum can query data in S3 directly【47†】, which is useful if we store Parquet files of financial data as well). Elasticsearch for search (managed Elastic Cloud or OpenSearch). Redis for caching (managed Redis via AWS ElastiCache or similar). If using GraphQL, a GraphQL engine like Hasura or Apollo Server could simplify some data fetching by auto-generating resolvers for Postgres, but that’s optional.
	•	Programming Languages: Python for ETL/NLP; TypeScript/JavaScript for front-end and possibly for backend API (Node). If the team prefers one language end-to-end, Python can also be used on backend (with FastAPI) and there are Python front-end frameworks (rare) or compilation to JS (not typical). It’s usually fine to use different languages for different pieces as long as team capability exists.
	•	NLP Tools: Use Hugging Face Transformers library in Python for sentiment (with a model like FinBERT or a custom-trained one). Possibly use spaCy for NER (maybe identify company names or industry terms in text). If we detect certain key terms like “going concern” or “material weakness”, those could be flags to highlight (these terms often signal problems). We can also use cloud NLP services if we want quick results without maintaining models; e.g., Amazon Comprehend has sentiment and key phrase extraction. However, a finance-specific model will give better results on filings (general sentiment models might misinterpret financial context).
	•	Charting Libraries: As discussed, D3.js for custom viz, Chart.js or ECharts for simpler charts. Also consider Highcharts which is very polished (but not free for commercial use unless licensed) or Plotly.js for interactive plots. We should ensure the library can integrate with React (many have React wrappers, e.g., react-chartjs-2).
	•	Authentication & Payments: Use secure libraries for auth. For example, if using Node, the Passport.js library can handle authentication strategies (we’ll likely have our own user/pass, plus maybe OAuth login with Google/GitHub for convenience). Passwords stored with bcrypt hashing. Manage user sessions or JWT tokens. For the paywall, integrate a payment processor like Stripe to handle subscriptions. Stripe can be configured to manage subscription plans (freemium vs premium) and webhooks to notify our system of subscription status changes. The backend then uses that to grant or revoke premium access in user accounts. Alternatively, if focusing B2B, we might do licensing contracts, but for retail Stripe is easiest.
	•	Monitoring & Logging: Choose a logging framework (winston for Node, or built-in logging in Python). Logs should go to a centralized system (maybe ELK stack, or simply CloudWatch Logs). Set up monitoring alarms (e.g., if ETL hasn’t run in X hours, or if website error rate spikes). Also, track usage analytics (what features users use, to inform product decisions – ensure privacy and compliance with something like Google Analytics or self-hosted Matomo).
	•	DevOps: Use Docker to package the app. Use CI/CD pipeline (GitHub Actions, Jenkins, etc.) to test and deploy new code. Infrastructure as Code (Terraform or CloudFormation) to manage cloud resources, so we can reproducibly set up dev/staging/prod environments and scale.

In summary, the tech stack might look like:
	•	Backend: Node.js + Express (TypeScript) OR Python + FastAPI, running on AWS ECS or EKS.
	•	Front-end: React/TypeScript deployed via CDN (S3 + CloudFront for static assets, for example).
	•	Data processing: Python scripts on Airflow or AWS Glue/Batch.
	•	Storage: AWS S3 (raw files), Postgres RDS (structured data), OpenSearch (text search), Redis (cache), Redshift (analytical queries).
	•	NLP/ML: Python with Transformers, possibly SageMaker for any training jobs, or using pre-trained models directly.

This stack leverages modern, widely-supported technologies ensuring maintainability and scalability.

Handling Data Updates and Changes

Keeping the data up-to-date is crucial since new filings occur daily. We will implement robust update mechanisms:
	•	Scheduled incremental updates: The ETL pipeline will run on a schedule (e.g., every hour or every night) to fetch new filings. SEDAR+ likely lists filings by date, so we can query “filings on [today’s date]” and get new ones. We maintain a marker of the last retrieved filing date/time to avoid duplication.
	•	If using an API from a provider, we could pull all filings since last check.
	•	If scraping, we might use RSS feeds if provided, or just scrape by date.
	•	We also handle weekends/holidays appropriately (the system might have no filings on those days, but insider trades can still be filed any day).
	•	Real-time notifications: If we want near-real-time updates (say within minutes of a filing appearing), we could run a lightweight process continuously checking or use any real-time push from the source if available. Since that may not exist publicly, a frequent poll is the fallback. This is usually sufficient as filings aren’t so high volume to overwhelm (we can poll every few minutes).
	•	Delta processing: When new data comes in, we process only that new data (instead of reprocessing everything). Our architecture should allow adding new records without redoing historical ones each time. Over time, we accumulate a large historical database but each day’s addition is manageable.
	•	Change detection: Sometimes filings get amended or corrected. We need to detect if a document we ingested is later replaced by a newer version. To handle this:
	•	Track unique identifiers or combination of (company, filing type, date) to identify duplicates.
	•	If we see a new filing that is labeled “Amended” or if the same report appears with a later date, we mark the old one as superseded in our DB.
	•	Possibly, reprocess the new version and update the structured data (for example, if an annual report was restated).
	•	We might keep both versions for audit trail, but present the latest as the primary data.
	•	Data quality monitoring: Implement checks in the pipeline: e.g., if a financial value seems off (net income is zero but revenue is huge, etc.), flag it to review if our parse missed something. Also monitor that the count of filings per day roughly matches expectations (to catch if our scraper missed a page due to an error).
	•	Regulatory compliance in updates: Ensure we do not miss filings to stay comprehensive. Also ensure timely removal if needed (if a document is removed by regulators or marked confidential, we should respect that – though public filings usually remain public).
	•	Compliance with SEDAR+ terms: We should verify if SEDAR+ has any terms about automated data collection. If required, we might need to throttle our requests to not hammer their servers, or even negotiate access if we become a heavy user. A partnership with CSA or using an approved data vendor feed might be necessary at scale. We will include a contact or attribution note like “Data sourced from SEDAR+ (www.sedarplus.ca)” if required, to be transparent.
	•	Scalability of updates: As data grows, ensure our update jobs still run within their window. If not, we can scale horizontally (e.g., process different companies in parallel) or vertically (use more powerful instance). The modular pipeline helps here (we could have one task fetch metadata of what’s new, then spawn tasks for each new file parse).

Security and Regulatory Considerations

Building a financial data platform requires attention to security and compliance:
	•	User Data Security: We will secure all user information (emails, passwords, payment info). Use strong encryption for passwords and any sensitive fields. Follow best practices like rate-limiting login attempts to prevent brute force, and possibly 2FA for account security of premium users.
	•	Data Privacy: While most data we handle is public filings, our platform might store user-specific data like watchlists or alert preferences. We will have a privacy policy and ensure we don’t sell or misuse that data. If we track user behavior (for improving the product), we’ll anonymize and aggregate it.
	•	Regulatory (financial): We must be careful that providing analytics does not cross into offering financial advice. We will include disclaimers that this is information and analysis platform, not a registered advisor, and that users should do their own research. If we plan on expanding features (like model portfolios or predictions), we may need to consider regulatory implications.
	•	Terms of Service of data sources: Ensure our use of SEDAR+ data doesn’t violate any terms. Historically, EDGAR data is free to reuse (public domain in the US), whereas SEDAR was operated by CSA which likely allows free use for investors, but we should double-check if any copyright exists on the documents themselves (likely not, but we should disclaim that the filings belong to the respective issuers and we’re just republishing). We might include links to original filings as a courtesy.
	•	Auditability: For enterprise/B2B customers, they might want to know data lineage. We will keep logs of data ingestion and a clear mapping from raw source to processed data. This also helps if a user spots a discrepancy – we can trace back to the original filing to verify.

Freemium Model Implementation

The platform will be offered in a freemium model – basic data access for free, advanced features for paid users. Here’s how we can implement and enforce this model:
	•	Free Tier Capabilities: Unregistered or free users can search and view filings and basic company info. They can download individual filings (after all, those are public records). They might see basic financial data and maybe one or two simple charts. However, we limit the depth and tools:
	•	For instance, free users can see the latest year’s financials, but not 10-year history trends without upgrading.
	•	They might get sentiment indicators on one report, but not historical sentiment trends or comparisons.
	•	They can see insider trades in a table, but maybe not the interactive dashboard or aggregated stats.
	•	No ability to set email alerts (or maybe 1 alert as a teaser).
	•	If the site has any community or save features (e.g., save a watchlist), that could be limited or require login at least.
	•	Premium Features: Subscribers get the full suite: advanced analytics dashboards, the ability to compare multiple companies, unlimited alerts, downloadable datasets, AI-generated summaries, etc. We can also have multiple tiers (e.g., a mid-tier for retail investors, and a higher-priced tier for professional or API access).
	•	Premium UI might have additional sections visible. We’ll manage this via the frontend (show/hide features based on user role) but also must secure on backend (don’t return premium data to non-premium users’ API calls).
	•	We might offer a trial period or certain features as “locked” with a prompt to upgrade when clicked.
	•	Payment and Subscription Management: As mentioned, integrating with Stripe or another payment gateway to handle recurring subscriptions is a straightforward solution. Stripe can manage credit card info securely (so we don’t store it) and send webhooks to our backend on successful payments, cancellations, etc. Our backend user model will have a field like is_premium and maybe premium_expiry date, which gets updated based on Stripe events. We’ll also build pages for users to manage their subscription (which might just embed Stripe’s customer portal to make it easy).
	•	B2B API Licensing: In addition to individual subscriptions, a revenue model could include B2B data licensing. For example, hedge funds or fintech apps might want raw access to our enriched data (via API or data dumps) without going through the UI. We could offer API keys for paid clients to pull data (with usage limits). This could be a separate enterprise tier. Technically, this means exposing certain endpoints specifically for bulk queries and ensuring the infrastructure can handle large requests. Rate limiting and monitoring will be important here, so one client doesn’t overwhelm the system.
	•	Advertising: While not explicitly asked, another monetization for free tier is ads. We could include some ads on the free version of the site (e.g., finance-related ads or affiliate links to brokerages). However, as a focused data platform, too many ads could detract from user experience. It’s an option to consider, possibly later or if needing additional revenue streams. Premium users would of course see no ads.
	•	Partnerships: We might partner with brokerage platforms or financial news sites. For instance, a broker could offer our premium analytics to their clients as a value-add (we get paid via the B2B deal). Or, we license our data feed to news websites for their own tools (some news sites might embed a widget showing the latest insider trades from our data – this drives awareness and could be a revenue share or API usage fee).
	•	Another partnership angle: academic or governmental. Perhaps universities could use the data for research (maybe at a discounted rate or open data collaboration for non-profit use).
	•	Given our focus is Canadian data, partnering with Canadian financial portals or forums (like investing forums) could also help spread the word.

The freemium model will be supported by clear UI cues – e.g., a “Pro” badge on premium features, an upgrade button, etc., to entice free users. We will analyze usage to decide what features drive upgrades and ensure we provide enough value in premium to justify the cost.

Conclusion and Further Considerations

We have outlined a comprehensive architecture for a Canadian market data platform using SEDAR+ filings. By ingesting the raw regulatory disclosures and layering on structured databases, search indices, and analytics algorithms, the platform can transform publicly available filings into actionable insights for investors. The architecture emphasizes scalability (using cloud services and parallel processing), performance (optimized databases and caching), and a modern user experience (interactive web app with rich visualizations). The freemium approach balances wide access to information with monetization of advanced analytics.

Going forward, critical success factors will include: maintaining high data quality, continuously updating the platform as SEDAR+ evolves or new data sources become available, and iterating on features based on user feedback. Since filings data can be “messy” and time-consuming to parse ￼, our engineering investment in robust ETL will pay off in differentiation. We also plan to stay updated with technology (for example, using the latest NLP advances for even better document analysis) to keep our analytics cutting-edge.

In summary, this platform will fill a gap for Canadian investors similar to what Quiver Quantitative did in the US – aggregating and democratizing data that was technically available but not easily digestible, and enriching it to unlock deeper insights. With the architecture and tools outlined above, we can build a service that is reliable, comprehensive, and insightful for all its users.

Sources:
	•	Canadian Securities Administrators – SEDAR+ overview and filings information ￼ ￼
	•	QuoteMedia – Description of SEDAR and types of filings (annual reports, MD&A, prospectuses, insider reports, etc.) ￼ ￼
	•	QuoteMedia – SEDAR filings available via API for integration ￼
	•	Datavid (2023) – Data ingestion architecture layers (ingestion, processing, storage, etc.) ￼
	•	AWS Machine Learning Blog (2021) – On the value and effort of parsing SEC filings for added features ￼
	•	Gibson Dunn (2017) – NLP in finance: MD&A as a target for sentiment analysis ￼


    Below is a data-first engineering plan that drills down on how to collect every public filing from SEDAR+, maps the raw web objects to a clean relational/analytical schema, and highlights the practical constraints (rate-limits, Terms-of-Use, licensing) you must design around.

⸻

1  | Understand what SEDAR+ actually exposes

1.1  Public website objects

Object in the UI	Hidden payload behind it	Evidence
Search Documents grid (30-row default page size)	HTML table plus a “Generate URL” link that resolves to a direct PDF download; full result list can be exported as CSV	￼ ￼
Reporting Issuers List (10 000 rows)	Paginated HTML list with an Export button that yields all issuer metadata as CSV	￼ ￼
Filing Inventory	Excel workbook listing every Filing Type → Document Type pair and its access level	￼
Legacy SEDAR Archive	Separate sub-domain (sedarplus.ca:5443) that still serves pre-2023 documents	￼
Profiles search and Industry Participant search services	/csa-party/service/create.html?service=searchProfiles etc. – return profile IDs that key every other call	￼

1.2  Legal guard-rails
	•	The Terms of Use prohibit “scraping” that replicates the public site, or creating a commercial product that is only the raw filings. You must either (a) negotiate a data-use licence with the CSA or (b) throttle requests, cache short-term, and transform content into analytics so the service is “more than a copy.”  ￼
	•	National Instrument 13-103 makes SEDAR+ the official record; amended filings supersede prior ones, so versioning is essential.  ￼

⸻

2  | Reverse-engineer the data feeds

2.1  High-value endpoints (no login required)

Purpose	How to hit it	Notes
CSV export of any search result	POST /csa-party/service/exportCsv with a JSON body identical to the form payload; returns a one-time URL	Hard quota: 30 PDFs per batch for anonymous users, but no explicit limit on CSV rows.  ￼
Document download	Use the “Generate URL” href captured in the CSV; it is a stable, public S3-style link	Works without cookies once issued.  ￼
Issuer universe	Hit “Export” on the Reporting Issuers List; columns = Issuer Number, Name, Jurisdiction(s), Type, In Default flag, Active CTO flag	10 000 rows, updated by each regulator.  ￼
Filing-type dictionary	Download the Filing Inventory workbook; each row = Category, Filing Type, Document Type, Access Level	Crucial for normalising document codes.  ￼

2.2  Session & pagination model
	1.	Stateless scrape: every request embeds _locale=en and a time-stamped viewInstance ID; the backend does not enforce CSRF on public searches.
	2.	Pagination token: the HTML grid uses start/page query params; simply iterate 1…n pages per day.
	3.	Rate-limit: back-off to 1 req/sec and parallelise across 4-6 IPs to stay polite; CSA can block if traffic is “frequent, public, commercial.”  ￼

⸻

3  | ETL design

3.1  Boot-strapping the historical lake

Stage	Tooling	Output
S0 – Seed issuer dimension	Python requests + pandas; ingest Reporting Issuers CSV	dim_issuer (PK = issuer_no)
S1 – Crawl 1997-2023 archive	Legacy sedar crawler (open-source GitHub repo for captcha bypass) as a one-off batch	Raw PDF dump (bronze)
S2 – Crawl SEDAR+ (2023→ today)	For each date d, call Search Documents with fromDate=d, export CSV, download PDFs in parallel	stg_filing_meta + document store
S3 – Parse	- PDFs → text via GROBID / Tika  |  - XBRL (if provided) via Arelle	fact_financials, fact_insiders …
S4 – Enrich	NLP (FinBERT sentiment), ratio calc, doc clustering	mart_analytics
S5 – Serve	Postgres (OLTP), ClickHouse (OLAP), OpenSearch (full-text)	GraphQL / REST API

3.2  Incremental daily job

DAG: etl_sedarplus_daily
 ├─ task: fetch_csv(dd-mm-yyyy)
 ├─ task: diff_against_filing_meta
 ├─ task-group: download_documents [async, max=10 concurrent]
 ├─ task: parse_and_load
 └─ task: update_analytics

Use Airflow (or MWAA) with SLA alerts if <95 % of yesterday’s docs arrive by 09:00 ET.

3.3  Handling amendments
	•	Key on (document_guid, version); if a new CSV row has the same GUID & later submitted_date, mark the earlier record superseded_by = new ID.
	•	Trigger re-parsing so downstream analytics stay consistent.

⸻

4  | Canonical schema (simplified)

dim_issuer(
  issuer_no PK,
  name,
  principal_jurisdiction,
  issuer_type,
  in_default BOOLEAN,
  active_cto BOOLEAN,
  first_seen, last_seen
)

dim_document_type(
  filing_category,
  filing_type,
  document_type,
  access_level
)

fact_filing(
  filing_id PK,
  issuer_no FK,
  document_guid,
  filing_type,
  document_type,
  submitted_date,
  url,
  size_bytes,
  version,
  superseded_by
)

fact_statement_line(
  filing_id FK,
  fiscal_period,
  line_item,
  value,
  currency
)

fact_insider_tx(
  issuer_no FK,
  insider_name,
  role,
  trade_date,
  txn_type,
  security,
  volume,
  price
)

mart_sentiment(
  filing_id FK,
  overall_score,
  positivity,
  negativity,
  uncertainty
)

Data dictionary sources
	•	Column sets in dim_document_type: from the Filing Inventory Excel.  ￼
	•	Issuer attributes in dim_issuer: from Reporting Issuers export.  ￼
	•	Filing metadata: columns available in CSV export (document name, size, submitted date, etc.).  ￼

⸻

5  | Compliance & licensing workflow
	1.	Throttle + cache during prototype.
	2.	Send a licence request to CSA Service Desk (sedarplus@csa-acvm.ca).
	•	They already issue “fee exception codes” for filers; similar channel is used for data questions.  ￼
	3.	Offer to supply analytics back to regulators (win-win) and request a higher bulk limit.
	4.	Add a Robots.txt honour flag in scraper; shut down automatically during the scheduled maintenance windows published on the site footer.  ￼ ￼
	5.	Display source attribution (“Document sourced from SEDAR+, © CSA 2025”) on every PDF viewer page to meet §2(a)(g) of the Terms of Use.  ￼

⸻

6  | Timeline & resourcing (MVP)

Month	Milestone	Team
1	Reverse-engineer endpoints, build scraper, ingest Filing Inventory + Issuer CSV; load to S3/Postgres	1 backend dev
2	Historical back-fill (legacy SEDAR) + daily Airflow DAG; basic React dashboard (search, download)	1 backend, 1 front-end
3	NLP sentiment pipeline, insider-trade merge (SEDI scraper), OLAP queries; start licence negotiation	2 backend, 1 data scientist
4	Freemium paywall (Stripe), alerts engine, scalable infra on AWS (Fargate/EKS)	whole team
5	Public launch (free tier) + marketing; iterate on premium analytics	all


⸻

7  | Next-step action items
	1.	Download the two official reference files today:
	•	Filing Inventory workbook.  ￼
	•	Reporting Issuers CSV.  ￼
	2.	Spin up a tiny EC2 box, capture one day’s Search Documents CSV (use fromDate=today) and store in S3.
	3.	Prototype parser: extract PDF text of one MD&A, run FinBERT, store score.
	4.	Draft an email to CSA Service Desk outlining your intended use and requesting throttle guidance.

With these steps you will have a legally-compliant ingestion pipeline, a data model ready for analytics, and a clear path to scale into a Quiver-style Canadian intelligence platform.