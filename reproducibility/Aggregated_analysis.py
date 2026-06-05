import os
import pandas as pd

"""This code compute aggregate metric considering all results in the log_metrics file"""

# Load and preprocess
folder = 'output_analysis'
file_name = 'log_metrics.csv'
file_path = os.path.join(folder, file_name)

# Load CSV
df = pd.read_csv(file_path)

# -------------------------
# Create "experiment" column
# -------------------------
df["experiment"] = df["file"].astype(str).apply(
    lambda x: "_".join(x.split("_")[:-1])
)

# -------------------------
# Aggregation rules
# -------------------------
agg_dict = {col: "mean" for col in df.columns if col not in ["file", "experiment"]}

# Override specific columns
agg_dict["Trucks_min_hour"] = "min"
agg_dict["Trucks_max_hour"] = "max"

# -------------------------
# Aggregate
# -------------------------
df_agg = df.groupby("experiment").agg(agg_dict).reset_index()

# -------------------------
# Save result
# -------------------------
df_agg.to_csv(file_path.replace("log_metrics", "aggregated_by_experiment"), index=False)

print(df_agg.head())