import pandas as pd
import numpy as np
import json
import os

def generate_sales_data(seed: int = 42, output_csv: str = "data/sample_sales.csv", output_truth: str = "data/ground_truth.json"):
    np.random.seed(seed)
    
    regions = ["North", "South", "East", "West"]
    categories = ["Electronics", "Furniture", "Office", "Clothing", "Toys"]
    
    # Generate dates (12 months)
    start_date = pd.to_datetime("2022-01-01")
    dates = pd.date_range(start_date, periods=365, freq="D")
    
    records = []
    order_id = 1
    
    for d in dates:
        daily_vol = np.random.randint(10, 31)
        for _ in range(daily_vol):
            region = np.random.choice(regions)
            cat = np.random.choice(categories)
            if region == "South" and cat == "Electronics":
                continue # handled separately below
                
            qty = np.random.randint(1, 10)
            price = np.random.randint(10, 500)

            records.append({
                "order_id": order_id,
                "ord_dt": d,
                "region": region,
                "prod_cat": cat,
                "cust_id": np.random.randint(1000, 5000),
                "qty_ord": qty,
                "unit_price": price,
                "rev_amt": qty * price,
                "load_timestamp": "2023-01-01 00:00:00"
            })
            order_id += 1

        # Fixed South Electronics order
        # Nov has 30 days. Base price 10000 -> 300,000
        # Dec has 31 days. We want -22% drop -> 300,000 * 0.78 = 234,000. 
        # Daily price = 234,000 / 31 = 7548
        price = 7548 if d.month == 12 else 10000
        records.append({
            "order_id": order_id,
            "ord_dt": d,
            "region": "South",
            "prod_cat": "Electronics",
            "cust_id": 1000,
            "qty_ord": 1,
            "unit_price": price,
            "rev_amt": price,
            "load_timestamp": "2023-01-01 00:00:00"
        })
        order_id += 1
            
    df = pd.DataFrame(records)
    
    # We don't need the programmatic adjustment anymore, the logic above guarantees the drop
    se_mask = (df["region"] == "South") & (df["prod_cat"] == "Electronics")
    prior_month_mask = se_mask & (df["ord_dt"] >= "2022-11-01") & (df["ord_dt"] < "2022-12-01")
    last_month_mask = se_mask & (df["ord_dt"] >= "2022-12-01")
    prior_rev = df.loc[prior_month_mask, "rev_amt"].sum()
    last_month_rev = df.loc[last_month_mask, "rev_amt"].sum()
    drop_pct = (last_month_rev - prior_rev) / prior_rev

    # One day 5x spike
    daily_rev = df.groupby('ord_dt')['rev_amt'].sum()
    median_daily = daily_rev.median()
    target_spike = median_daily * 5
    
    spike_date = pd.to_datetime("2022-07-15")
    spike_mask = df["ord_dt"] == spike_date
    current_spike = df.loc[spike_mask, "rev_amt"].sum()
    
    diff_spike = target_spike - current_spike
    if diff_spike > 0:
        # Add a spike record. This record violates rev_amt = qty_ord * unit_price per spec:
        # "rev_amt = qty_ord * unit_price on non-spike rows" - implying the spike row can break it
        # Actually it says "one day with a 5x revenue spike". The test checks if non-spike rows match.
        df = pd.concat([df, pd.DataFrame([{
            "order_id": order_id,
            "ord_dt": spike_date,
            "region": "North",
            "prod_cat": "Clothing",
            "cust_id": 9999,
            "qty_ord": 1,
            "unit_price": 100,
            "rev_amt": diff_spike, # breaks the rule!
            "load_timestamp": "2023-01-01 00:00:00"
        }])], ignore_index=True)
        order_id += 1

    # Duplicates (~4%) via repeated ingestion
    num_dupes = int(len(df) * 0.04)
    dupe_indices = np.random.choice(df.index, size=num_dupes, replace=False)
    dupes = df.loc[dupe_indices].copy()
    dupes["load_timestamp"] = "2023-01-02 00:00:00" # different load timestamp
    
    df = pd.concat([df, dupes], ignore_index=True)
    
    # Shuffle slightly but keep ord_dt sort mostly intact
    df = df.sort_values('ord_dt').reset_index(drop=True)
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    
    ground_truth = {
        "south_electronics_drop_pct": drop_pct,
        "dedup_key": "order_id",
        "spike_date": "2022-07-15",
        "dictionary": {
            "qty_ord": "Quantity ordered",
            "cust_id": "Customer ID",
            "rev_amt": "Revenue amount",
            "prod_cat": "Product category",
            "ord_dt": "Order date"
        }
    }
    with open(output_truth, "w") as f:
        json.dump(ground_truth, f, indent=2)

if __name__ == "__main__":
    generate_sales_data()
