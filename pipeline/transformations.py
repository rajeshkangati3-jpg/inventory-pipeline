import duckdb

def recompute_daily_balances(conn: duckdb.DuckDBPyConnection, min_affected_date: str):
    if not min_affected_date:
        return

    conn.execute("DELETE FROM fact_daily_inventory_balance WHERE balance_date >= ?", [min_affected_date])

    conn.execute("""
    CREATE TEMP TABLE IF NOT EXISTS date_spine AS
    WITH date_range AS (
        SELECT CAST(MIN(movement_timestamp) AS DATE) as start_d, 
               CAST(MAX(movement_timestamp) AS DATE) as end_d
        FROM stg_inventory_movements
    ),
    all_dates AS (
        SELECT UNNEST(generate_series(start_d, end_d, INTERVAL 1 DAY))::DATE as balance_date
        FROM date_range
    ),
    entities AS (
        SELECT DISTINCT location_id, sku_id FROM stg_inventory_movements
    )
    SELECT d.balance_date, e.location_id, e.sku_id
    FROM all_dates d
    CROSS JOIN entities e;
    """)

    conn.execute("""
    CREATE TEMP TABLE IF NOT EXISTS daily_aggregates AS
    SELECT 
        CAST(movement_timestamp AS DATE) as balance_date,
        location_id,
        sku_id,
        SUM(CASE WHEN movement_type IN ('RECEIPT', 'TRANSFER_IN') THEN quantity ELSE 0 END) as total_receipts,
        SUM(CASE WHEN movement_type IN ('ISSUE', 'TRANSFER_OUT') THEN quantity ELSE 0 END) as total_issues,
        SUM(CASE WHEN movement_type = 'ADJUSTMENT' THEN quantity ELSE 0 END) as total_adjustments
    FROM stg_inventory_movements
    GROUP BY 1, 2, 3;
    """)

    conn.execute("""
    INSERT INTO fact_daily_inventory_balance
    WITH full_daily_summary AS (
        SELECT 
            s.balance_date,
            s.location_id,
            s.sku_id,
            COALESCE(a.total_receipts, 0) as total_receipts,
            COALESCE(a.total_issues, 0) as total_issues,
            COALESCE(a.total_adjustments, 0) as total_adjustments,
            (COALESCE(a.total_receipts, 0) - COALESCE(a.total_issues, 0) + COALESCE(a.total_adjustments, 0)) as net_daily_change
        FROM date_spine s
        LEFT JOIN daily_aggregates a 
            ON s.balance_date = a.balance_date 
           AND s.location_id = a.location_id 
           AND s.sku_id = a.sku_id
    ),
    running_totals AS (
        SELECT 
            balance_date,
            location_id,
            sku_id,
            total_receipts,
            total_issues,
            total_adjustments,
            net_daily_change,
            SUM(net_daily_change) OVER (
                PARTITION BY location_id, sku_id 
                ORDER BY balance_date 
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) as running_closing
        FROM full_daily_summary
    )
    SELECT 
        balance_date,
        location_id,
        sku_id,
        (running_closing - net_daily_change) as opening_balance,
        total_receipts,
        total_issues,
        total_adjustments,
        running_closing as closing_balance,
        CURRENT_TIMESTAMP as updated_at
    FROM running_totals
    WHERE balance_date >= ?;
    """, [min_affected_date])

    conn.execute("DROP TABLE IF EXISTS date_spine;")
    conn.execute("DROP TABLE IF EXISTS daily_aggregates;")
