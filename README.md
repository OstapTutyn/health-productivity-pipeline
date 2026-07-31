# Personal Routine & Productivity Data Pipeline

An end-to-end automated data engineering pipeline designed to ingest, transform, and centralize personal metrics from multi-source ecosystems into a PostgreSQL data warehouse (Supabase) using a multi-layered architecture.

## 🏗️ Architecture & Data Flow

The pipeline follows a structured data flow model:
1. **Bronze Layer (Raw Ingestion):** Collects raw JSON payloads directly from external APIs and device exports with incremental watermarking.
2. **Silver Layer (Transformation & Cleansing):** Normalizes raw data, handles batch chunking (`upsert` optimization), standardizes categories, and populates structured analytical tables.
3. **Orchestration & CI/CD:** Fully automated via **GitHub Actions** on a daily schedule, ensuring seamless background execution without local intervention.

---

## 🛠️ Tech Stack & Integrations

- **Core & Infrastructure:** 
  - Python 3.10+
  - Supabase (PostgreSQL Data Warehouse)
  - GitHub Actions (CI/CD Orchestration)
- **Data Sources & APIs:**
  - **Last.fm & Trax Scrobbler:** Music listening history tracking.
  - **Notion API:** Journaling and personal productivity logs.
  - **iPhone Screen Time & Active Watch:** Device usage and screen time metrics.
  - **Google Fit:** Health and physical activity tracking from Apple Watch.

---

## 📁 Project Structure

```text
personal-routine-pipeline/
│
├── .github/
│   └── workflows/
│       └── pipeline.yml       # GitHub Actions automated schedule
├── sql/
│   ├── bronze/                
│   │   └── 01_create_bronze_tables.sql
│   └── silver/                
│       └── 01_create_silver_tables.sql
├── src/
│   ├── ingestion/             # API extractors and file parsers
│   │   ├── google_fit_ingest.py
│   │   ├── iphone_ingest.py
│   │   ├── music_ingest.py
│   │   ├── notion_ingest.py
│   │   └── screentime_ingest.py
│   ├── transformation/        # Cleansing, aggregation, and loading scripts
│   │   ├── health_transform.py
│   │   ├── music_to_silver.py
│   │   ├── notion_transform.py
│   │   ├── screentime_to_events.py
│   │   └── screentime_to_hourly.py
│   └── utils/
│       └── check_iphone_pipeline.py
├── requirements.txt
└── .gitignore
