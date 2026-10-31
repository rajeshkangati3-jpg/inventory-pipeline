import pytest
import os
import pandas as pd
import duckdb
from pipeline.db import init_tables
from pipeline.ingestion import process_file

@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test_warehouse.duckdb")
    conn = duckdb.connect(db_file)
    init_tables(conn)
    yield conn, db_file
    conn.close()

def test_happy_path(test_db, tmp_path):
    conn, db_file = test_db
    csv_file = str(tmp_path / "happy.csv")
    
    df = pd.DataFrame([{
        "movement_id": "M1",
        "movement_timestamp": "2026-10-01T10:00:00",
        "location_id": "LOC1",
        "sku_id": "SKU1",
        "movement_type": "RECEIPT",
        "quantity": 100.0,
        "reference_id": "R1"
    }])
    df.to_csv(csv_file, index=False)

    process_file(csv_file, conn)

    result = conn.execute("SELECT closing_balance FROM fact_daily_inventory_balance WHERE sku_id='SKU1'").fetchone()
    assert result[0] == 100.0

def test_empty_input(test_db, tmp_path):
    conn, db_file = test_db
    csv_file = str(tmp_path / "empty.csv")
    
    df = pd.DataFrame(columns=["movement_id", "movement_timestamp", "location_id", "sku_id", "movement_type", "quantity", "reference_id"])
    df.to_csv(csv_file, index=False)

    process_file(csv_file, conn)
    
    count = conn.execute("SELECT COUNT(*) FROM stg_inventory_movements").fetchone()[0]
    assert count == 0

def test_malformed_and_null_records(test_db, tmp_path):
    conn, db_file = test_db
    csv_file = str(tmp_path / "malformed.csv")
    
    data = [
        {"movement_id": "M1", "movement_timestamp": "2026-10-01T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "RECEIPT", "quantity": "ABC", "reference_id": "R1"},
        {"movement_id": "", "movement_timestamp": "2026-10-01T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "RECEIPT", "quantity": 50, "reference_id": "R2"},
        {"movement_id": "M3", "movement_timestamp": "2026-10-01T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "INVALID_TYPE", "quantity": 50, "reference_id": "R3"}
    ]
    pd.DataFrame(data).to_csv(csv_file, index=False)

    process_file(csv_file, conn)

    q_count = conn.execute("SELECT COUNT(*) FROM quarantine_movements").fetchone()[0]
    valid_count = conn.execute("SELECT COUNT(*) FROM stg_inventory_movements").fetchone()[0]
    
    assert q_count == 3
    assert valid_count == 0

def test_idempotency_rerun(test_db, tmp_path):
    conn, db_file = test_db
    csv_file = str(tmp_path / "idempotent.csv")
    
    df = pd.DataFrame([{
        "movement_id": "M1",
        "movement_timestamp": "2026-10-01T10:00:00",
        "location_id": "LOC1",
        "sku_id": "SKU1",
        "movement_type": "RECEIPT",
        "quantity": 100.0,
        "reference_id": "R1"
    }])
    df.to_csv(csv_file, index=False)

    process_file(csv_file, conn)
    process_file(csv_file, conn)

    stg_count = conn.execute("SELECT COUNT(*) FROM stg_inventory_movements").fetchone()[0]
    balance = conn.execute("SELECT closing_balance FROM fact_daily_inventory_balance WHERE sku_id='SKU1'").fetchone()[0]
    
    assert stg_count == 1
    assert balance == 100.0

def test_domain_edge_case_backdated_recalculation(test_db, tmp_path):
    conn, db_file = test_db
    
    f1 = str(tmp_path / "day1_2.csv")
    pd.DataFrame([
        {"movement_id": "M1", "movement_timestamp": "2026-10-01T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "RECEIPT", "quantity": 100, "reference_id": "R1"},
        {"movement_id": "M2", "movement_timestamp": "2026-10-02T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "ISSUE", "quantity": 30, "reference_id": "R2"}
    ]).to_csv(f1, index=False)
    process_file(f1, conn)

    bal_day2 = conn.execute("SELECT closing_balance FROM fact_daily_inventory_balance WHERE balance_date='2026-10-02' AND sku_id='SKU1'").fetchone()[0]
    assert bal_day2 == 70.0

    f2 = str(tmp_path / "backdated.csv")
    pd.DataFrame([
        {"movement_id": "M3", "movement_timestamp": "2026-10-01T15:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "RECEIPT", "quantity": 50, "reference_id": "R3"}
    ]).to_csv(f2, index=False)
    process_file(f2, conn)

    bal_day1_new = conn.execute("SELECT closing_balance FROM fact_daily_inventory_balance WHERE balance_date='2026-10-01' AND sku_id='SKU1'").fetchone()[0]
    bal_day2_new = conn.execute("SELECT closing_balance FROM fact_daily_inventory_balance WHERE balance_date='2026-10-02' AND sku_id='SKU1'").fetchone()[0]

    assert bal_day1_new == 150.0
    assert bal_day2_new == 120.0

def test_domain_edge_case_negative_adjustments(test_db, tmp_path):
    conn, db_file = test_db
    csv_file = str(tmp_path / "adjustment.csv")
    
    pd.DataFrame([
        {"movement_id": "M1", "movement_timestamp": "2026-10-01T10:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "RECEIPT", "quantity": 100, "reference_id": "R1"},
        {"movement_id": "M2", "movement_timestamp": "2026-10-01T12:00:00", "location_id": "LOC1", "sku_id": "SKU1", "movement_type": "ADJUSTMENT", "quantity": -25, "reference_id": "R2"}
    ]).to_csv(csv_file, index=False)

    process_file(csv_file, conn)

    res = conn.execute("SELECT total_adjustments, closing_balance FROM fact_daily_inventory_balance WHERE sku_id='SKU1'").fetchone()
    assert res[0] == -25.0
    assert res[1] == 75.0
