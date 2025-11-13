#!/usr/bin/env python3

"""
Fairness test: Compare Qdrant vs Weaviate dengan recall yang setara
"""

import json
import time
import numpy as np
from clients import QdrantClientHelper, WeaviateClient
from datasets import make_or_load_dataset
from utils import brute_force_topk, recall_at_k

def run_fairness_test():
    print("=== FAIRNESS TEST: QDRANT vs WEAVIATE ===")
    
    # Load dataset
    vectors, queries, *_ = make_or_load_dataset(
        root="/datasets",
        name="cohere-mini-50k-d768",
        n=3000,  # Same limit for both
        dim=768,
        n_queries=1000,
        seed=42,
        pdf_dir="",
        embedder="sentence-transformers",
        enable_payload=False,
        enable_hybrid=False,
    )
    
    print(f"Loaded {len(vectors)} vectors, {len(queries)} queries")
    
    # Ground truth for recall calculation
    gt_idx = brute_force_topk(vectors, queries[:64], 10, metric="COSINE")
    
    results = {}
    
    # Test Qdrant (default ef=64)
    print("\n--- Testing Qdrant ---")
    qc = QdrantClientHelper()
    conn_q = qc.connect()
    
    qc.drop_recreate(conn_q, "fairness_test", 768, "Cosine", on_disk=True)
    qc.insert(conn_q, "fairness_test", vectors)
    
    # Measure Qdrant performance
    latencies_q = []
    start_time = time.time()
    for i in range(10):
        t_start = time.time()
        res_q = qc.search(conn_q, "fairness_test", queries[:10], 10, ef_search=64)
        t_end = time.time()
        latencies_q.append((t_end - t_start) * 1000)
    
    total_time_q = time.time() - start_time
    qps_q = 100 / total_time_q  # 10 queries * 10 iterations
    
    # Calculate recall
    res_idx_q = qc.search(conn_q, "fairness_test", queries[:64], 10, ef_search=64)
    recall_q = recall_at_k(gt_idx, res_idx_q)
    
    results['qdrant'] = {
        'qps': qps_q,
        'recall': recall_q,
        'p99_latency_ms': np.percentile(latencies_q, 99),
        'mean_latency_ms': np.mean(latencies_q)
    }
    
    print(f"Qdrant QPS: {qps_q:.1f}")
    print(f"Qdrant Recall: {recall_q:.3f}")
    print(f"Qdrant P99 Latency: {np.percentile(latencies_q, 99):.2f}ms")
    
    # Test Weaviate with ef=192 (to match Qdrant recall)
    print("\n--- Testing Weaviate (ef=192) ---")
    wh = WeaviateClient()
    conn_w = wh.connect()
    
    wh.drop_recreate(conn_w, "FairnessTest", 768, "cosine", ef=192)
    wh.insert(conn_w, "FairnessTest", vectors)
    time.sleep(2)  # Allow indexing
    
    # Measure Weaviate performance
    latencies_w = []
    start_time = time.time()
    for i in range(10):
        t_start = time.time()
        res_w = wh.search(conn_w, "FairnessTest", queries[:10], 10, ef=192, hybrid=False)
        t_end = time.time()
        latencies_w.append((t_end - t_start) * 1000)
    
    total_time_w = time.time() - start_time
    qps_w = 100 / total_time_w
    
    # Calculate recall
    res_idx_w = wh.search(conn_w, "FairnessTest", queries[:64], 10, ef=192, hybrid=False)
    recall_w = recall_at_k(gt_idx, res_idx_w)
    
    results['weaviate_ef192'] = {
        'qps': qps_w,
        'recall': recall_w,
        'p99_latency_ms': np.percentile(latencies_w, 99),
        'mean_latency_ms': np.mean(latencies_w)
    }
    
    print(f"Weaviate QPS: {qps_w:.1f}")
    print(f"Weaviate Recall: {recall_w:.3f}")
    print(f"Weaviate P99 Latency: {np.percentile(latencies_w, 99):.2f}ms")
    
    # Summary
    print("\n=== FAIRNESS COMPARISON ===")
    print(f"Qdrant (ef=64):     QPS={results['qdrant']['qps']:.1f}, Recall={results['qdrant']['recall']:.3f}, P99={results['qdrant']['p99_latency_ms']:.1f}ms")
    print(f"Weaviate (ef=192):  QPS={results['weaviate_ef192']['qps']:.1f}, Recall={results['weaviate_ef192']['recall']:.3f}, P99={results['weaviate_ef192']['p99_latency_ms']:.1f}ms")
    
    # Performance ratio
    qps_ratio = results['qdrant']['qps'] / results['weaviate_ef192']['qps']
    print(f"\nQPS Ratio (fair comparison): {qps_ratio:.1f}×")
    
    # Save results
    with open('/app/results/fairness_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

if __name__ == "__main__":
    run_fairness_test()