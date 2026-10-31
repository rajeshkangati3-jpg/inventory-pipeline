import argparse
from pipeline.db import get_db_connection

def run_reconciliation(db_path: str):
    conn = get_db_connection(db_path)
    
    print("\n--- 1. Source Movement Aggregates vs Fact Daily Totals ---")
    recon_df = conn.execute("""
        WITH movement_totals AS (
            SELECT 
                SUM(CASE WHEN movement_type IN ('RECEIPT', 'TRANSFER_IN') THEN quantity ELSE 0 END) as raw_receipts,
                SUM(CASE WHEN movement_type IN ('ISSUE', 'TRANSFER_OUT') THEN quantity ELSE 0 END) as raw_issues,
                SUM(CASE WHEN movement_type = 'ADJUSTMENT' THEN quantity ELSE 0 END) as raw_adjustments
            FROM stg_inventory_movements
        ),
        fact_totals AS (
            SELECT 
                SUM(total_receipts) as snapshot_receipts,
                SUM(total_issues) as snapshot_issues,
                SUM(total_adjustments) as snapshot_adjustments
            FROM fact_daily_inventory_balance
        )
        SELECT 
            m.raw_receipts, f.snapshot_receipts, (m.raw_receipts - f.snapshot_receipts) as receipt_diff,
            m.raw_issues, f.snapshot_issues, (m.raw_issues - f.snapshot_issues) as issue_diff,
            m.raw_adjustments, f.snapshot_adjustments, (m.raw_adjustments - f.snapshot_adjustments) as adj_diff
        FROM movement_totals m, fact_totals f;
    """).fetchdf()
    print(recon_df.to_string(index=False))

    print("\n--- 2. Daily Balance Continuity Check (Opening == Prior Closing) ---")
    continuity_check = conn.execute("""
        WITH balance_lag AS (
            SELECT 
                location_id,
                sku_id,
                balance_date,
                opening_balance,
                LAG(closing_balance) OVER (PARTITION BY location_id, sku_id ORDER BY balance_date) as prev_closing
            FROM fact_daily_inventory_balance
        )
        SELECT * FROM balance_lag
        WHERE prev_closing IS NOT NULL AND opening_balance != prev_closing;
    """).fetchdf()

    if continuity_check.empty:
        print("[SUCCESS] All daily opening balances perfectly match prior closing balances!")
    else:
        print(f"[FAIL] Found {len(continuity_check)} continuity discrepancies:")
        print(continuity_check.to_string())

    print("\n--- 3. Quarantine Breakdown ---")
    q_summary = conn.execute("""
        SELECT quarantine_reason, COUNT(*) as record_count 
        FROM quarantine_movements 
        GROUP BY 1 
        ORDER BY 2 DESC;
    """).fetchdf()
    print(q_summary.to_string(index=False))

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="warehouse.duckdb")
    args = parser.parse_args()
    run_reconciliation(args.db)
