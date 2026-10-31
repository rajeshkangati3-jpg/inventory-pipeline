import argparse
import random
import csv
import uuid
from datetime import datetime, timedelta

def generate_synthetic_movements(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    
    locations = ["LOC_NORTH", "LOC_SOUTH", "LOC_EAST", "LOC_WEST"]
    skus = [f"SKU_100{i}" for i in range(1, 11)]
    types = ["RECEIPT", "ISSUE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT"]
    
    start_date = datetime(2026, 10, 1)
    records = []
    
    generated_ids = []

    for i in range(count):
        if generated_ids and random.random() < 0.02:
            mov_id = random.choice(generated_ids)
        else:
            mov_id = f"MOV-{uuid.UUID(int=random.getrandbits(128))}"
            generated_ids.append(mov_id)

        is_malformed = random.random() < 0.03
        
        days_offset = random.randint(0, 15)
        if random.random() < 0.05:
            days_offset = random.randint(0, 5)
            
        event_time = start_date + timedelta(days=days_offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))

        loc = random.choice(locations) if not (is_malformed and random.random() < 0.5) else ""
        sku = random.choice(skus) if not (is_malformed and random.random() < 0.5) else ""
        m_type = random.choice(types) if not (is_malformed and random.random() < 0.3) else "INVALID_TYPE"
        qty = round(random.uniform(1.0, 500.0), 2)
        
        if m_type == "ADJUSTMENT" and random.random() < 0.5:
            qty = -qty

        records.append({
            "movement_id": mov_id,
            "movement_timestamp": event_time.isoformat(),
            "location_id": loc,
            "sku_id": sku,
            "movement_type": m_type,
            "quantity": qty if not is_malformed else "NOT_A_NUMBER",
            "reference_id": f"REF-{random.randint(1000, 9999)}"
        })

    return records

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic inventory movement dataset.")
    parser.add_argument("--count", type=int, default=1000, help="Number of records to generate")
    parser.add_argument("--output", type=str, default="sample_data.csv", help="Output CSV path")
    args = parser.parse_args()

    data = generate_synthetic_movements(args.count)
    fieldnames = ["movement_id", "movement_timestamp", "location_id", "sku_id", "movement_type", "quantity", "reference_id"]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"Successfully generated {len(data)} records in '{args.output}'.")

if __name__ == "__main__":
    main()
