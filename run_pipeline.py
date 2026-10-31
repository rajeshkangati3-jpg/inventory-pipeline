import argparse
import time
from pipeline.db import get_db_connection
from pipeline.ingestion import process_file

def main():
    parser = argparse.ArgumentParser(description="Run Inventory Pipeline Ingestion.")
    parser.add_argument("--input", type=str, required=True, help="Path to input CSV file")
    parser.add_argument("--db", type=str, default="warehouse.duckdb", help="DuckDB file path")
    args = parser.parse_args()

    print(f"[*] Connecting to database: {args.db}")
    conn = get_db_connection(args.db)

    start = time.time()
    print(f"[*] Processing file: {args.input}")
    
    try:
        run_id = process_file(args.input, conn)
        elapsed = time.time() - start
        
        run_summary = conn.execute(
            "SELECT total_records_processed, valid_records_ingested, quarantined_records, status FROM pipeline_runs WHERE run_id = ?",
            [run_id]
        ).fetchone()

        print("\n================ PIPELINE EXECUTION SUMMARY ================")
        print(f" Run ID          : {run_id}")
        print(f" Execution Time  : {elapsed:.3f} seconds")
        print(f" Total Processed : {run_summary[0]}")
        print(f" Valid Ingested  : {run_summary[1]}")
        print(f" Quarantined     : {run_summary[2]}")
        print(f" Status          : {run_summary[3]}")
        print("============================================================\n")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
