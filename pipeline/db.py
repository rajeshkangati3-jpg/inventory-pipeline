import duckdb

def get_db_connection(db_path: str = "warehouse.duckdb"):
    conn = duckdb.connect(db_path)
    init_tables(conn)
    return conn

def init_tables(conn: duckdb.DuckDBPyConnection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id VARCHAR PRIMARY KEY,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        source_file VARCHAR,
        total_records_processed INTEGER,
        valid_records_ingested INTEGER,
        quarantined_records INTEGER,
        status VARCHAR,
        failure_reason VARCHAR
    );
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS quarantine_movements (
        movement_id VARCHAR,
        movement_timestamp VARCHAR,
        location_id VARCHAR,
        sku_id VARCHAR,
        movement_type VARCHAR,
        quantity VARCHAR,
        reference_id VARCHAR,
        source_file VARCHAR,
        quarantine_reason VARCHAR,
        quarantined_at TIMESTAMP
    );
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS stg_inventory_movements (
        movement_id VARCHAR PRIMARY KEY,
        movement_timestamp TIMESTAMP,
        location_id VARCHAR,
        sku_id VARCHAR,
        movement_type VARCHAR,
        quantity DECIMAL(18,4),
        reference_id VARCHAR,
        source_file VARCHAR,
        ingested_at TIMESTAMP
    );
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS fact_daily_inventory_balance (
        balance_date DATE,
        location_id VARCHAR,
        sku_id VARCHAR,
        opening_balance DECIMAL(18,4),
        total_receipts DECIMAL(18,4),
        total_issues DECIMAL(18,4),
        total_adjustments DECIMAL(18,4),
        closing_balance DECIMAL(18,4),
        updated_at TIMESTAMP,
        PRIMARY KEY (balance_date, location_id, sku_id)
    );
    """)
