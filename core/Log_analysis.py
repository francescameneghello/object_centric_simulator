import os
import pandas as pd
import glob
import numpy as np
import ast  # to safely parse relation_ships


"""This code compute relevant metric over each simulated log in the output folder"""

# Folder
folder = 'output'

# Pattern: all files like simulated_log_order_process_*.csv
pattern = os.path.join(folder, 'simulated_log_*.csv')

results = []

# Loop over files
for file_path in glob.glob(pattern):
    print(f"Processing: {file_path}")

    # Load CSV
    df = pd.read_csv(file_path)

    # -------------------------
    # Preprocessing
    # -------------------------

    # Remove completely empty rows
    df = df.dropna(how='all')

    # Remove rows with only empty strings/whitespace
    df = df.replace(r'^\s*$', pd.NA, regex=True).dropna(how='all')

    # Create object column
    df["object"] = df["id_case"].astype(str).str.split("_").str[0]

    # Define start and end times
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])

    metrics = {"file": os.path.basename(file_path)}

    # -------------------------
    # (1) Total execution time
    # -------------------------
    total_time = df["end_time"].max() - df["start_time"].min()
    metrics["total_execution_time_seconds"] = total_time.total_seconds()

    # -------------------------
    # (2) Count "Load"
    # -------------------------
    df_load = df[df["activity"] == "Load"]
    metrics["Load_count"] = len(df_load)

    # -------------------------
    # (//) Count Trucks
    # -------------------------
    df_prepare = df[df["activity"] == "Prepare"]
    metrics["Trucks_count"] = len(df_prepare)

    # -------------------------
    # (///) Count Truck resources
    # -------------------------
    # Filter only "truck" objects
    df_truck = df[df["object"] == "truck"].copy()
    metrics["Trucks_resources"] = df_truck["resource"].nunique()

    # -------------------------
    # (/\/) Count Truck
    # -------------------------
    # Extract hour from timestamps
    df_truck["hour"] = pd.to_datetime(df_truck["start_time"]).dt.hour
    # Compute min and max hour
    metrics["Trucks_min_hour"] = df_truck["hour"].min()
    metrics["Trucks_max_hour"] = df_truck["hour"].max()


    # -------------------------
    # (3) relation_ships size stats for "Load", count how many items are in the relation_ships
    # -------------------------
    def count_elements(x):
        try:
            parsed = ast.literal_eval(x)
            return len(parsed)
        except:
            return np.nan

    load_sizes = df_load["relation_ships"].dropna().apply(count_elements).dropna()

    if len(load_sizes) > 0:
        metrics.update({
            "Load_items_min": load_sizes.min(),
            "Load_items_max": load_sizes.max(),
            "Load_items_median": load_sizes.median(),
            "Load_items_avg": load_sizes.mean(),
            "Load_items_std": load_sizes.std()
        })
    else:
        metrics.update({
            "Load_items_min": np.nan,
            "Load_items_max": np.nan,
            "Load_items_median": np.nan,
            "Load_items_avg": np.nan,
            "Load_items_std": np.nan
        })

    # -------------------------
    # (4) Count Delivered cases
    # -------------------------
    df_delivered = df[df["activity"] == "Delivered"]
    delivered_cases = df_delivered["id_case"].unique()
    metrics["Delivered_items_count"] = len(delivered_cases)

    # -------------------------
    # (5) Time from Packing → Delivered
    # -------------------------
    df_packing = df[df["activity"] == "Packing"][["id_case", "start_time"]]
    df_del = df[df["activity"] == "Delivered"][["id_case", "end_time"]]

    merged = pd.merge(df_del, df_packing, on="id_case", how="inner")

    time_diffs = (merged["end_time"] - merged["start_time"]).dt.total_seconds()

    if len(time_diffs) > 0:
        metrics.update({
            "Item_delivery_time_min": time_diffs.min(),
            "Item_delivery_time_max": time_diffs.max(),
            "Item_delivery_time_median": time_diffs.median(),
            "Item_delivery_time_avg": time_diffs.mean(),
            "Item_delivery_time_std": time_diffs.std()
        })
    else:
        metrics.update({
            "Item_delivery_time_min": np.nan,
            "Item_delivery_time_max": np.nan,
            "Item_delivery_time_median": np.nan,
            "Item_delivery_time_avg": np.nan,
            "Item_delivery_time_std": np.nan
        })

    # -------------------------
    # (5b) Delivered on a different day than Packing
    # -------------------------
    if len(merged) > 0:
        # Extract dates (ignore time)
        packing_dates = merged["start_time"].dt.date
        delivered_dates = merged["end_time"].dt.date

        # Boolean: delivered on a different day
        different_day = packing_dates != delivered_dates

        # Count how many
        diff_day_count = different_day.sum()

        # Total delivered (same denominator you used before)
        total_delivered = len(merged)

        # Percentage
        diff_day_percentage = diff_day_count / total_delivered

        metrics.update({
            "delivered_diff_day_count": diff_day_count,
            "delivered_diff_day_percentage": diff_day_percentage
        })
    else:
        metrics.update({
            "delivered_diff_day_count": np.nan,
            "delivered_diff_day_percentage": np.nan
        })

    # -------------------------
    # (6) Count orders
    # -------------------------
    df_order = df[df["activity"] == "Place Order"]
    order_cases = df_order["id_case"].unique()
    metrics["Order_count"] = len(order_cases)

    # -------------------------
    # (7) Unique cases for "Add Item"
    # -------------------------
    df_add = df[df["activity"] == "Add Item"]
    metrics["Add_Item_orders"] = df_add["id_case"].nunique()

    # -------------------------
    # (8) Unique relation_ships for "Remove Item"
    # -------------------------
    df_remove = df[df["activity"] == "Remove Item"]
    metrics["Remove_Item_orders"] = df_remove["relation_ships"].nunique()

    # -------------------------
    # (9) Count of "Close order"
    # -------------------------
    df_close_order = df[df["activity"] == "Close Order"]
    metrics["Close_order_count"] = len(df_close_order)

    # Save metrics for this file
    results.append(metrics)

# -------------------------
# Final output
# -------------------------
results_df = pd.DataFrame(results)

output_path = os.path.join(folder, "log_metrics.csv")
results_df.to_csv(output_path, index=False)

print("All files processed")
