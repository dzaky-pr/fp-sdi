# /bench/analyze_results.py
import json, matplotlib.pyplot as plt, pandas as pd, os

def analyze_results(results_file, output_dir="results"):
    os.makedirs(output_dir, exist_ok=True)

    with open(results_file, 'r') as f:
        content = f.read()

    json_start = content.rfind('[')
    if json_start == -1:
        raise ValueError(f"No JSON array found in {results_file}")

    data = json.loads(content[json_start:])
    df = pd.DataFrame(data)
    cols = set(df.columns)

    # Plot QPS vs Concurrency (selalu ada)
    if {"conc","qps"}.issubset(cols):
        plt.figure(figsize=(10,6))
        plt.plot(df['conc'], df['qps'], marker='o')
        plt.xlabel('Concurrency'); plt.ylabel('QPS'); plt.title('QPS vs Concurrency'); plt.grid(True)
        plt.savefig(f"{output_dir}/qps_concurrency.png"); plt.close()

    # Plot P99 vs Concurrency (opsional)
    if {"conc","p99"}.issubset(cols):
        plt.figure(figsize=(10,6))
        plt.plot(df['conc'], df['p99'], marker='o')
        plt.xlabel('Concurrency'); plt.ylabel('P99 Latency (ms)'); plt.title('P99 Latency vs Concurrency'); plt.grid(True)
        plt.savefig(f"{output_dir}/p99_concurrency.png"); plt.close()

    # Plot I/O bandwidth (pakai kolom yang ada)
    io_col = "avg_bandwidth_mb_s" if "avg_bandwidth_mb_s" in cols else ("io_bw" if "io_bw" in cols else None)
    if io_col and "conc" in cols:
        plt.figure(figsize=(10,6))
        plt.plot(df['conc'], df[io_col], marker='o')
        plt.xlabel('Concurrency'); plt.ylabel('I/O Bandwidth (MB/s)'); plt.title('I/O Bandwidth vs Concurrency'); plt.grid(True)
        plt.savefig(f"{output_dir}/io_bandwidth_concurrency.png"); plt.close()

    # Plot Read/Write (opsional)
    if {"conc","read_mb","write_mb"}.issubset(cols):
        plt.figure(figsize=(10,6))
        plt.plot(df['conc'], df['read_mb'], marker='o', label='Read MB')
        plt.plot(df['conc'], df['write_mb'], marker='o', label='Write MB')
        plt.xlabel('Concurrency'); plt.ylabel('Data Transfer (MB)'); plt.title('Read/Write Data Transfer vs Concurrency')
        plt.legend(); plt.grid(True); plt.savefig(f"{output_dir}/read_write_concurrency.png"); plt.close()

    # Summary
    max_qps = df['qps'].max() if 'qps' in cols else None
    min_p99 = df['p99'].min() if 'p99' in cols else None
    avg_cpu = df['cpu'].mean() if 'cpu' in cols else None
    avg_io_bandwidth = df[io_col].mean() if io_col else 0.0

    # Bottleneck heuristics
    qps_decline = False
    if 'qps' in cols and 'conc' in cols and len(df) > 1:
        qps_decline = df['qps'].iloc[-1] < df['qps'].iloc[0] * 0.5
    high_cpu = (avg_cpu is not None) and (avg_cpu > 80)
    high_io  = avg_io_bandwidth > 100  # heuristik NVMe

    if qps_decline and high_cpu:
        bottleneck = "CPU-bound (high CPU usage + declining QPS)"
    elif qps_decline and high_io:
        bottleneck = "I/O-bound (high I/O bandwidth + declining QPS)"
    elif high_cpu:
        bottleneck = "CPU-bound (high CPU usage)"
    elif high_io:
        bottleneck = "I/O-bound (high I/O bandwidth)"
    else:
        bottleneck = "Well-balanced (no clear bottleneck detected)"

    summary = {
        "max_qps": max_qps,
        "min_p99": min_p99,
        "avg_cpu": avg_cpu,
        "avg_io_bandwidth_mb_s": avg_io_bandwidth,
        "bottleneck_analysis": bottleneck
    }
    with open(f"{output_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Analysis complete. Plots saved in {output_dir}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, nargs='+', help="Path to results JSON files")
    ap.add_argument("--output", default="results", help="Output directory base")
    args = ap.parse_args()
    for results_file in args.results:
        output_dir = f"{args.output}/{os.path.basename(results_file).replace('.json', '')}"
        analyze_results(results_file, output_dir)
