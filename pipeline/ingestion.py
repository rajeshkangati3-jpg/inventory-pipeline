import uuid
import pandas as pd
from datetime import datetime
import duckdb
from .validation import validate_dataframe
from .transformations import recompute_daily_balances

def process_file(source_file_path: str, conn: duckdb.DuckDBPyConnection) -> str:
    run_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    try:
        df = pd.read_csv(source_file_path)
    except Exception as e:
        conn.execute("""
        INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (run_id, start_time, datetime.utcnow(), source_file_path, 0, 0, 0, "FAILED", str(e)))
        raise RuntimeError(f"Failed to read CSV input: {e}")

    total_records = len(df)
    
    valid_df, quarantine_df = validate_dataframe(df, source_file_path)
    
    if not quarantine_df.empty:
        quarantine_df["quarantined_at"] = datetime.utcnow()
        conn.register("tmp_quarantine", quarantine_df)
        conn.execute("""
        INSERT INTO quarantine_movements 
        SELECT movement_id, movement_timestamp, location_id, sku_id, movement_type, 
               CAST(quantity AS VARCHAR), reference_id, source_file, quarantine_reason, quarantined_at 
        FROM tmp_quarantine;
        """)
        conn.unregister("tmp_quarantine")

    valid_count = len(valid_df)
    quarantine_count = len(quarantine_df)

    if valid_count > 0:
        valid_df["source_file"] = source_file_path
        valid_df["ingested_at"] = datetime.utcnow()
        valid_df["quantity"] = valid_df["quantity"].astype(float)
        valid_df["movement_timestamp"] = pd.to_datetime(valid_df["movement_timestamp"])

        min_affected_date = valid_df["movement_timestamp"].dt.date.min().isoformat()

        conn.register("tmp_valid", valid_df)
        conn.execute("""
        INSERT INTO stg_inventory_movements
        SELECT movement_id, movement_timestamp, location_id, sku_id, movement_type, quantity, reference_id, source_file, ingested_at
        FROM tmp_valid
        ON CONFLICT (movement_id) DO UPDATE SET
            movement_timestamp = EXCLUDED.movement_timestamp,
            location_id = EXCLUDED.location_id,
            sku_id = EXCLUDED.sku_id,
            movement_type = EXCLUDED.movement_type,
            quantity = EXCLUDED.quantity,
            reference_id = EXCLUDED.reference_id,
            source_file = EXCLUDED.source_file,
            ingested_at = EXCLUDED.ingested_at;
        """)
        conn.unregister("tmp_valid")

        recompute_daily_balances(conn, min_affected_date)

    end_time = datetime.utcnow()
    conn.execute("""
    INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (run_id, start_time, end_time, source_file_path, total_records, valid_count, quarantine_count, "SUCCESS", None))

    return run_id
