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
    
    # Plot I/O Bandwidth vs Concurrency
    plt.figure(figsize=(10, 6))
    plt.plot(df['conc'], df['avg_bandwidth_mb_s'], marker='o', label='I/O Bandwidth (MB/s)', color='purple')
    plt.xlabel('Concurrency')
    plt.ylabel('I/O Bandwidth (MB/s)')
    plt.title('I/O Bandwidth vs Concurrency')
    plt.grid(True)
    plt.savefig(f"{output_dir}/io_bandwidth_concurrency.png")
    plt.close()
    
    # Plot Read/Write MB vs Concurrency
    plt.figure(figsize=(10, 6))
    plt.plot(df['conc'], df['read_mb'], marker='o', label='Read MB', color='blue')
    plt.plot(df['conc'], df['write_mb'], marker='o', label='Write MB', color='red')
    plt.xlabel('Concurrency')
    plt.ylabel('Data Transfer (MB)')
    plt.title('Read/Write Data Transfer vs Concurrency')
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{output_dir}/read_write_concurrency.png")
    plt.close()
    
    # Summary stats
    max_qps = df['qps'].max()
    min_p99 = df['p99'].min()
    avg_cpu = df['cpu'].mean()
    avg_io_bandwidth = df['avg_bandwidth_mb_s'].mean()
    
    # Improved bottleneck analysis
    qps_decline = (df['qps'].iloc[-1] < df['qps'].iloc[0] * 0.5) if len(df) > 1 else False
    high_cpu = avg_cpu > 80
    high_io = avg_io_bandwidth > 100  # Assuming NVMe can do >100 MB/s
    
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
    ap.add_argument("--results", required=True, help="Path to results JSON file")
    ap.add_argument("--output", default="results", help="Output directory")
    args = ap.parse_args()
    analyze_results(args.results, args.output)