# Daily Inventory Balance & Movement Reconciliation Pipeline

## 1. Overview & Architecture
This pipeline processes inventory transactions (**Receipts**, **Issues**, **Transfers**, and **Adjustments**) into daily closing inventory balances. It is built to support late-arriving and backdated events by executing snapshot recalibrations for affected dates, ensuring deterministic daily balances.

### Data Flow Diagram
```text
[ CSV / Data Generator ] 
          │
          ▼
┌──────────────────────────┐
│  Schema & Rules Engine   │ ──► [ Reject Storage / Quarantine Table ]
└─────────┬────────────────┘
          │ (Valid Records)
          ▼
┌──────────────────────────┐
│   Raw Movements Staging  │
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Backdated Snapshot Logic │ ──► Recalculate balances from min(affected_date) -> today
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Daily Balances Fact Table│
└──────────────────────────┘
```

## 2. Source & Target Schemas

### Source: `stg_inventory_movements`
- `movement_id` (VARCHAR, PK): Unique deterministic ID for transaction.
- `movement_timestamp` (TIMESTAMP): Event timestamp (ISO-8601).
- `location_id` (VARCHAR, FK): Warehouse/Location identifier.
- `sku_id` (VARCHAR, FK): Stock Keeping Unit identifier.
- `movement_type` (VARCHAR): Enum (`RECEIPT`, `ISSUE`, `TRANSFER_IN`, `TRANSFER_OUT`, `ADJUSTMENT`).
- `quantity` (DECIMAL): Quantity moved.
- `reference_id` (VARCHAR, Optional): External identifier (PO, SO, Adjustment note).
- `source_file` (VARCHAR): Metadata for lineage tracking.
- `ingested_at` (TIMESTAMP): Pipeline processing timestamp.

### Target: `fact_daily_inventory_balance`
- `balance_date` (DATE, Composite PK): Daily snap date.
- `location_id` (VARCHAR, Composite PK): Location code.
- `sku_id` (VARCHAR, Composite PK): SKU code.
- `opening_balance` (DECIMAL): Beginning of day quantity.
- `total_receipts` (DECIMAL): Sum of RECEIPTs + TRANSFER_INs.
- `total_issues` (DECIMAL): Sum of ISSUEs + TRANSFER_OUTs.
- `total_adjustments` (DECIMAL): Sum of ADJUSTMENTs (positive or negative).
- `closing_balance` (DECIMAL): End of day quantity (`opening + receipts - issues + adjustments`).
- `updated_at` (TIMESTAMP): System audit timestamp.

## 3. Key Design Choices & Trade-offs
1. **DuckDB In-Memory/File Engine**: Selected for vectorized query performance and zero-dependency local operation. Scales smoothly up to tens of millions of rows.
2. **Backdated Correction Strategy**: Instead of naive incremental aggregation, when a late event arrives for date `T`, the pipeline identifies the earliest backdated timestamp and recalculates daily balances from `T` forward to `max(date)`.
3. **Idempotency & Deduplication**: Upserts are executed using deterministic `movement_id` keying. Batch execution logs track run metadata (`run_id`, processing counts, failure reason).

## 4. Setup & Running Instructions

### Step 1: Initialize Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Generate Sample Data (Small & Large Scale)
```bash
# Generate 1,000 baseline records with intentional anomalies & backdated events
python generate_data.py --count 1000 --output sample_data.csv

# Generate 100,000+ records for high-volume stress testing
python generate_data.py --count 100000 --output large_data.csv
```

### Step 3: Execute Ingestion Pipeline
```bash
python run_pipeline.py --input sample_data.csv --db warehouse.duckdb
```

### Step 4: Run Output Validation & Reconciliation Report
```bash
python validate_output.py --db warehouse.duckdb
```

### Step 5: Run Automated Test Suite
```bash
pytest tests/
```
