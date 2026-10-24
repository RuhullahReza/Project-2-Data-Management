> Classification: INTERNAL

# Project 2 - Data Management

## Setup

1. Start Postgres

   ```bash
   docker compose up -d
   ```

2. Copy the DDL ke container

   ```bash
   docker cp .\DDL.sql data-management-postgres:/tmp/DDL.sql
   ```

3. Execute DDL

   ```bash
   docker exec data-management-postgres psql -U postgres -d data_management -v ON_ERROR_STOP=1 -f /tmp/DDL.sql
   ```
