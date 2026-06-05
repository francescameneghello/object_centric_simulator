import os
import pandas as pd
import glob
import numpy as np
import ast  # to safely parse relationships

file = "output_log/simulated_log_full_from_spec_0.csv"
#file = "output_log/simulated_log_process_order_toy_0.csv"
df = pd.read_csv(file)

# parse datetime columns
df["start_time"] = pd.to_datetime(df["start_time"])
df["end_time"] = pd.to_datetime(df["end_time"])

# extract object type (order / item / truck)
df["object_type"] = df["role"].str.replace("Role ", "", regex=False)

# compute duration per object type
result = (
    df.groupby("object_type")
      .agg(
          start_min=("start_time", "min"),
          end_max=("end_time", "max")
      )
)

result["duration"] = result["end_max"] - result["start_min"]

# optional: convert to seconds
result["duration_seconds"] = result["duration"].dt.total_seconds()

# save output CSV
result.reset_index().to_csv("object_level_kpis.csv", index=False)

print(result)