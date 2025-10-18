import time, math, statistics, numpy as np, subprocess, os
from typing import List, Tuple

def pct(xs: List[float], p: float) -> float:
    if not xs: return float('nan')
    a = sorted(xs)
    k = (len(a)-1) * p
    f = math.floor(k); c = math.ceil(k)
    if f == c: return a[int(k)]
    return a[f] + (a[c]-a[f])*(k-f)

def percentiles(lat_ms: List[float]) -> dict:
    return {
        "p50": pct(lat_ms, 0.50),
        "p95": pct(lat_ms, 0.95),
        "p99": pct(lat_ms, 0.99),
        "avg": statistics.fmean(lat_ms) if lat_ms else float('nan'),
    }

def brute_force_topk(vectors: np.ndarray, queries: np.ndarray, topk: int, metric="IP") -> np.ndarray:
    # Simple brute-force for small datasets to compute ground-truth
    # Returns indices shape (n_queries, topk)
    if metric.upper() in ("IP","COSINE"):
        sims = queries @ vectors.T
    else:  # L2 small trick
        # dist^2 = ||q||^2 + ||x||^2 - 2 q·x ; we only need ranking
        qq = np.sum(queries**2, axis=1, keepdims=True)
        xx = np.sum(vectors**2, axis=1)
        sims = -(qq + xx - 2*queries@vectors.T)
    return np.argpartition(-sims, kth=topk-1, axis=1)[:, :topk]  # topk (unsorted)

def recall_at_k(gt_idx: np.ndarray, res_idx: np.ndarray) -> float:
    # both shape (nq, topk)
    hit = 0
    for i in range(gt_idx.shape[0]):
        hit += len(set(gt_idx[i]).intersection(set(res_idx[i])))
    return hit / (gt_idx.shape[0]*gt_idx.shape[1])

def flush_page_cache():
    """Flush page cache before experiments"""
    commands = [
        "sync",
        "echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true",
        "echo 2 > /proc/sys/vm/drop_caches 2>/dev/null || true", 
        "echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true"
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd, shell=True, timeout=10)
            time.sleep(0.5)
        except:
            pass  # Continue even if flush fails (permission issues)
    
    print("Page cache flush attempted")
