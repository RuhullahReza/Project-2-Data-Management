> Classification: INTERNAL

# Project 2 - Data Management

## Setup

1. Start Postgres

   ```bash
   docker compose up -d
   ```

2. Copy DDL ke container

   ```bash
   docker cp .\DDL.sql data-management-postgres:/tmp/DDL.sql
   ```

3. Execute DDL

   ```bash
   docker exec data-management-postgres psql -U postgres -d data_management -v ON_ERROR_STOP=1 -f /tmp/DDL.sql
   ```

## Python Environment

1. Virtual environment

   ```bash
   python -m venv .venv
   ```

2. Aktivasi

   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1

   # macOS / Linux
   source .venv/bin/activate
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

