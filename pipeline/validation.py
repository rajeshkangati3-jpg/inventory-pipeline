import pandas as pd
from typing import Tuple

VALID_TYPES = {"RECEIPT", "ISSUE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT"}

def validate_dataframe(df: pd.DataFrame, source_file: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    quarantine_list = []
    valid_rows = []
    seen_ids = set()

    for idx, row in df.iterrows():
        reasons = []
        mov_id = str(row.get("movement_id", "")).strip()
        
        if not mov_id or mov_id.lower() == "nan":
            reasons.append("Missing movement_id")
        elif mov_id in seen_ids:
            reasons.append("Duplicate movement_id in batch")
        
        if not str(row.get("location_id", "")).strip():
            reasons.append("Missing location_id")
        if not str(row.get("sku_id", "")).strip():
            reasons.append("Missing sku_id")

        try:
            pd.to_datetime(row.get("movement_timestamp"))
        except Exception:
            reasons.append("Invalid timestamp format")

        m_type = str(row.get("movement_type", "")).strip()
        if m_type not in VALID_TYPES:
            reasons.append(f"Invalid movement_type: '{m_type}'")

        try:
            qty = float(row.get("quantity"))
            if pd.isna(qty):
                reasons.append("Quantity is null/NaN")
        except Exception:
            reasons.append("Non-numeric quantity")

        if reasons:
            q_row = row.to_dict()
            q_row["source_file"] = source_file
            q_row["quarantine_reason"] = "; ".join(reasons)
            quarantine_list.append(q_row)
        else:
            seen_ids.add(mov_id)
            valid_rows.append(row.to_dict())

    valid_df = pd.DataFrame(valid_rows)
    quarantine_df = pd.DataFrame(quarantine_list)

    return valid_df, quarantine_df
