import argparse
from pathlib import Path
import pandas as pd
import numpy as np


ANALYSIS_ROOT = Path(__file__).resolve().parent

def find_log_files(experiment_name: str):
    log_dir = ANALYSIS_ROOT / "experiments" / experiment_name / "output_log"

    if not log_dir.exists():
        raise FileNotFoundError(f"Log directory not found: {log_dir}")

    csv_files = sorted(list(log_dir.glob("*.csv")))

    if len(csv_files) == 0:
        raise FileNotFoundError(f"No CSV files found in {log_dir}")

    return csv_files


def compute_stats(df: pd.DataFrame) -> dict:
    for col in ["enabled_time", "start_time", "end_time"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    n_objects = df["obj_id"].nunique()
    n_events = len(df)

    start = df["enabled_time"].min()
    end = df["end_time"].max()
    duration = end - start

    activity_counts = df["activity"].value_counts()

    return {
        "total_objects": n_objects,
        "total_events": n_events,
        "simulation_start": start,
        "simulation_end": end,
        "simulation_duration": duration,
        "most_common_activity": activity_counts.index[0],
        "most_common_activity_count": int(activity_counts.iloc[0]),
    }


def analyze_single(file_path: Path):
    df = pd.read_csv(file_path)
    return compute_stats(df)

def analyze_multiple(files: list[Path]):
    results = []

    for f in files:
        df = pd.read_csv(f)
        stats = compute_stats(df)
        stats["file"] = f.name
        results.append(stats)

    res_df = pd.DataFrame(results)

    numeric_cols = [
        "total_objects",
        "total_events",
        "simulation_duration",
        "most_common_activity_count",
    ]

    # convert duration to seconds for aggregation
    res_df["simulation_duration"] = res_df["simulation_duration"].dt.total_seconds()

    aggregated = {
        "runs": len(res_df),
        "avg_total_objects": res_df["total_objects"].mean(),
        "std_total_objects": res_df["total_objects"].std(),
        "avg_total_events": res_df["total_events"].mean(),
        "std_total_events": res_df["total_events"].std(),
        "avg_duration_sec": res_df["simulation_duration"].mean(),
        "std_duration_sec": res_df["simulation_duration"].std(),
    }

    return aggregated, res_df


def save_single(stats: dict, experiment_name: str):
    out_dir = ANALYSIS_ROOT / "experiments" / experiment_name / "output_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / "statistics.csv"
    pd.DataFrame([stats]).to_csv(out_file, index=False)

    print(f"\nSaved single-run statistics to: {out_file}")


def save_aggregated(agg: dict, detailed_df: pd.DataFrame, experiment_name: str):
    out_dir = ANALYSIS_ROOT / "experiments" / experiment_name / "output_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    agg_file = out_dir / "aggregated_statistics.csv"
    detail_file = out_dir / "run_details.csv"

    pd.DataFrame([agg]).to_csv(agg_file, index=False)
    detailed_df.to_csv(detail_file, index=False)

    print(f"\nSaved aggregated statistics to: {agg_file}")
    print(f"Saved run-level details to: {detail_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_name")
    args = parser.parse_args()

    files = find_log_files(args.experiment_name)

    print(f"Found {len(files)} log file(s).")

    if len(files) == 1:
        print("Running single-run analysis...")
        stats = analyze_single(files[0])
        save_single(stats, args.experiment_name)

    else:
        print("Running aggregated multi-run analysis...")
        agg, detailed = analyze_multiple(files)
        save_aggregated(agg, detailed, args.experiment_name)


if __name__ == "__main__":
    main()