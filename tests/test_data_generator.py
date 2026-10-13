import pytest
import os
import pandas as pd
import json
from evals.generate_data import generate_sales_data

def test_data_generator(tmp_path):
    out_csv = tmp_path / "sample_sales.csv"
    out_json = tmp_path / "ground_truth.json"
    
    generate_sales_data(seed=42, output_csv=str(out_csv), output_truth=str(out_json))
    
    assert os.path.exists(out_csv)
    assert os.path.exists(out_json)
    
    df = pd.read_csv(out_csv)
    with open(out_json, "r") as f:
        truth = json.load(f)
        
    # duplicate rate 4% +/-0.5
    dup_mask = df.duplicated(subset=[c for c in df.columns if c != "load_timestamp"], keep=False)
    # wait, the spec says "duplicate via repeated ingestion (second load timestamp)". 
    # That means the rows are identical EXCEPT maybe the load_timestamp. 
    # Or maybe they are completely exact duplicates?
    # Spec: "about 4% of rows duplicated via repeated ingestion (second load timestamp)". 
    # So dupes are identical except for load_timestamp.
    # We will identify them by order_id or just excluding load_timestamp.
    
    # 1. Duplicate rate
    base_cols = [c for c in df.columns if c != 'load_timestamp']
    num_dupes = df.duplicated(subset=base_cols, keep='first').sum()
    total_unique = len(df.drop_duplicates(subset=base_cols))
    dup_rate = num_dupes / total_unique
    assert 0.035 <= dup_rate <= 0.045, f"Duplicate rate {dup_rate} out of bounds"
    
    # 2. South Electronics down 22% +/-1
    df['ord_dt'] = pd.to_datetime(df['ord_dt'])
    # Get last month and prior month
    max_date = df['ord_dt'].max()
    last_month_start = max_date.replace(day=1)
    prior_month_end = last_month_start - pd.Timedelta(days=1)
    prior_month_start = prior_month_end.replace(day=1)
    
    se_df = df[(df['region'] == 'South') & (df['prod_cat'] == 'Electronics') & ~df.duplicated(subset=base_cols)]
    last_month_rev = se_df[se_df['ord_dt'] >= last_month_start]['rev_amt'].sum()
    prior_month_rev = se_df[(se_df['ord_dt'] >= prior_month_start) & (se_df['ord_dt'] <= prior_month_end)]['rev_amt'].sum()
    
    drop_pct = (last_month_rev - prior_month_rev) / prior_month_rev
    assert -0.23 <= drop_pct <= -0.21, f"Drop % {drop_pct} out of bounds"
    
    # 3. Exactly one day above 4x median daily revenue
    daily_rev = df[~df.duplicated(subset=base_cols)].groupby('ord_dt')['rev_amt'].sum()
    median_daily = daily_rev.median()
    spikes = daily_rev[daily_rev > 4 * median_daily]
    assert len(spikes) == 1
    spike_date = spikes.index[0].strftime("%Y-%m-%d")
    assert spike_date == truth["spike_date"]
    
    # 4. rev_amt = qty_ord * unit_price on non-spike rows
    # The spec says "exactly one day with a 5x revenue spike" and "rev_amt = qty_ord * unit_price on non-spike rows". 
    # We'll check that non-spike rows have the exact match.
    non_spike_df = df[(df['ord_dt'].dt.strftime('%Y-%m-%d') != spike_date)]
    assert (non_spike_df['rev_amt'] == non_spike_df['qty_ord'] * non_spike_df['unit_price']).all()
    
    # 5. ground truth matches
    assert abs(truth["south_electronics_drop_pct"] - drop_pct) < 0.001
    assert truth["dedup_key"] == "order_id"  # example dedup key
    
def test_data_generator_deterministic(tmp_path):
    generate_sales_data(seed=10, output_csv=str(tmp_path / "1.csv"), output_truth=str(tmp_path / "1.json"))
    generate_sales_data(seed=10, output_csv=str(tmp_path / "2.csv"), output_truth=str(tmp_path / "2.json"))
    
    with open(tmp_path / "1.csv") as f1, open(tmp_path / "2.csv") as f2:
        assert f1.read() == f2.read()
