from dataclasses import dataclass

@dataclass
class PipelineConfig:
    db_path: str = "warehouse.duckdb"
    valid_movement_types: tuple = ("RECEIPT", "ISSUE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT")
