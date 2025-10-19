# bench/analyze_results.py
import json, matplotlib.pyplot as plt, pandas as pd, os

def analyze_results(results_file, output_dir="results"):
    os.makedirs(output_dir, exist_ok=True)
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Plot QPS vs Concurrency
    plt.figure(figsize=(10, 6))
    plt.plot(df['conc'], df['qps'], marker='o', label='QPS')
    plt.xlabel('Concurrency')
    plt.ylabel('QPS')
    plt.title('QPS vs Concurrency')
    plt.grid(True)
    plt.savefig(f"{output_dir}/qps_concurrency.png")
    plt.close()
    
    # Plot P99 vs Concurrency
    plt.figure(figsize=(10, 6))
    plt.plot(df['conc'], df['p99'], marker='o', label='P99 Latency (ms)', color='red')
    plt.xlabel('Concurrency')
    plt.ylabel('P99 Latency (ms)')
    plt.title('P99 Latency vs Concurrency')
    plt.grid(True)
    plt.savefig(f"{output_dir}/p99_concurrency.png")
    plt.close()
    
    # Plot CPU vs Concurrency
    plt.figure(figsize=(10, 6))
    plt.plot(df['conc'], df['cpu'], marker='o', label='CPU Usage (%)', color='green')
    plt.xlabel('Concurrency')
    plt.ylabel('CPU Usage (%)')
    plt.title('CPU Usage vs Concurrency')
    plt.grid(True)
    plt.savefig(f"{output_dir}/cpu_concurrency.png")
    plt.close()
    
    # Summary stats
    summary = {
        "max_qps": df['qps'].max(),
        "min_p99": df['p99'].min(),
        "avg_cpu": df['cpu'].mean(),
        "bottleneck_analysis": "CPU-bound if QPS decreases sharply with concurrency" if df['qps'].iloc[-1] < df['qps'].iloc[0] * 0.5 else "I/O-bound"
    }
    
    with open(f"{output_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Analysis complete. Plots saved in {output_dir}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="Path to results JSON file")
    ap.add_argument("--output", default="results", help="Output directory")
    args = ap.parse_args()
    analyze_results(args.results, args.output)