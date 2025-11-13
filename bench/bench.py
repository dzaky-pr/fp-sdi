# /bench/bench.py
#!/usr/bin/env python3
import argparse, json, os, time, threading, numpy as np
from datetime import datetime
from clients import QdrantClientHelper, WeaviateClient
from monitoring import IOMonitor, sample_container_cpu
from utils import brute_force_topk, recall_at_k

# ---------------------------------------------------------
# Utility
# ---------------------------------------------------------
def log(msg):
    ts = datetime.now().strftime("[%H:%M:%S]")
    print(f"{ts} {msg}", flush=True)


# ---------------------------------------------------------
# Global time budget
# ---------------------------------------------------------
WALL_START = time.time()


def time_left(budget_s):
    return budget_s - (time.time() - WALL_START)


def budget_enough(budget_s, need):
    return time_left(budget_s) >= need


# ---------------------------------------------------------
# Main concurrency runner
# ---------------------------------------------------------
def run_concurrency_grid(container_name, run_seconds, queries, search_callable,
                         budget_s=300, disable_monitor=False):
    results = []
    total_conc = len(CONF["concurrency_grid"])
    total_runs = total_conc * CONF.get("repeats", 1)
    run_count = 0

    for conc in CONF["concurrency_grid"]:
        if not budget_enough(budget_s, run_seconds + 2):
            break
        for repeat in range(CONF.get("repeats", 1)):
            if not budget_enough(budget_s, run_seconds + 2):
                break

            run_count += 1
            log(f"[{container_name}] Concurrency {conc}, repeat {repeat+1}/{CONF.get('repeats', 1)}")

            # Warm-up kecil, abaikan error
            try:
                warmup_result = search_callable(queries[:min(64, len(queries))], 1, conc)
                _ = warmup_result[0] if isinstance(warmup_result, tuple) else warmup_result
                time.sleep(0.3)
            except Exception as e:
                log(f"[{container_name}] Warm-up failed: {e}")

            # I/O monitoring
            io_monitor = IOMonitor()
            io_thread = threading.Thread(target=lambda: None)
            if not disable_monitor:
                io_thread = io_monitor.start_monitoring(run_seconds)

            # CPU monitoring
            cpu_values = []
            cpu_monitoring = True
            def cpu_thread_fn():
                while cpu_monitoring:
                    cpu_pct = sample_container_cpu(container_name, 1)
                    if cpu_pct > 0:
                        cpu_values.append(cpu_pct)
                    time.sleep(0.2)
            cpu_thread = threading.Thread(target=cpu_thread_fn, daemon=True)
            if not disable_monitor:
                cpu_thread.start()

            # Run benchmark with latency tracking
            t0 = time.time()
            result = search_callable(queries, run_seconds, conc)
            if isinstance(result, tuple) and len(result) == 2:
                qps, latencies = result
            else:
                qps = result
                latencies = []
            elapsed = time.time() - t0

            # Stop monitors
            cpu_monitoring = False
            if not disable_monitor:
                io_monitor.stop_monitoring()
            io_thread.join(timeout=1)
            cpu_thread.join(timeout=1)

            cpu_mean = float(np.mean(cpu_values)) if cpu_values else 0.0
            io_stats = io_monitor.parse_bandwidth() if not disable_monitor else {}
            io_bw    = float(io_stats.get('avg_bandwidth_mb_s', 0.0))
            read_mb  = float(io_stats.get('read_mb', 0.0))
            write_mb = float(io_stats.get('write_mb', 0.0))

            # Calculate latency percentiles
            latency_stats = {}
            if latencies and len(latencies) > 0:
                latency_stats = {
                    "min_latency_ms": float(np.min(latencies)) * 1000,
                    "mean_latency_ms": float(np.mean(latencies)) * 1000,
                    "p50_latency_ms": float(np.percentile(latencies, 50)) * 1000,
                    "p95_latency_ms": float(np.percentile(latencies, 95)) * 1000,
                    "p99_latency_ms": float(np.percentile(latencies, 99)) * 1000,
                    "max_latency_ms": float(np.max(latencies)) * 1000,
                }
            else:
                latency_stats = {
                    "min_latency_ms": None,
                    "mean_latency_ms": None,
                    "p50_latency_ms": None,
                    "p95_latency_ms": None,
                    "p99_latency_ms": None,
                    "max_latency_ms": None,
                }

            results.append({
                "conc": conc,
                "qps": qps,
                "cpu": cpu_mean,
                "avg_bandwidth_mb_s": io_bw,
                "read_mb": read_mb,
                "write_mb": write_mb,
                "elapsed": elapsed,
                **latency_stats  # Add latency statistics
            })
    return results


# ---------------------------------------------------------
# Database runners
# ---------------------------------------------------------
def run_qdrant(ds, vec_override=None, qry_override=None):
    qc = QdrantClientHelper()
    conn = qc.connect()

    # Load dataset (gunakan make_or_load_dataset dari config)
    from datasets import make_or_load_dataset
    vectors, queries, *_ = make_or_load_dataset(
        root=CONF.get("data_root", "../datasets"),
        name=ds["name"],
        n=ds["n_vectors"],
        dim=ds["dim"],
        n_queries=ds["n_queries"],
        seed=CONF.get("seed", 42),
        pdf_dir=CONF.get("pdf_dir") or "",
        embedder=CONF.get("embedder", "sentence-transformers"),
        enable_payload=CONF.get("enable_payload_filter", False),
        enable_hybrid=CONF.get("enable_hybrid_search", False),
    )
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override

    qc.drop_recreate(conn, "bench", ds["dim"], "Cosine", on_disk=True)
    qc.insert(conn, "bench", vectors)  # ← hapus payload=True yang salah

    # Ground-truth untuk recall
    gt_q  = int(CONF.get("gt_queries_for_recall", 128))
    gt_idx = brute_force_topk(vectors, queries[:gt_q], CONF["topk"], metric="COSINE")

    # Sensitivity study: test different ef values
    if ARGS.sensitivity:
        ef_values = [64, 128, 192, 256]
        all_results = []
        
        for ef in ef_values:
            log(f"[Qdrant] Testing ef_search={ef}")
            
        # callable yang menghormati concurrency dan track latency
        def search_callable(qs, secs, conc):
            from concurrent.futures import ThreadPoolExecutor, as_completed
            stop_at = time.time() + secs
            chunks = np.array_split(qs, conc)
            all_latencies = []
            
            def worker(batch):
                done = 0
                worker_latencies = []
                while time.time() < stop_at:
                    t_start = time.time()
                    _ = qc.search(conn, "bench", batch, CONF["topk"], ef_search=ef)
                    t_end = time.time()
                    worker_latencies.append(t_end - t_start)
                    done += len(batch)
                return done, worker_latencies
                
            total = 0
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = [ex.submit(worker, b) for b in chunks if len(b) > 0]
                for fu in as_completed(futs):
                    worker_total, worker_latencies = fu.result()
                    total += worker_total
                    all_latencies.extend(worker_latencies)
            
            return total / float(secs), all_latencies

        results = run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable,
                                       budget_s=ARGS.budget_s, disable_monitor=ARGS.no_monitor)

        # Calculate recall for this ef
        res_idx = qc.search(conn, "bench", queries[:min(64, gt_q)], CONF["topk"], ef_search=ef)
        recall = recall_at_k(gt_idx[:min(64, gt_q)], res_idx)
        log(f"[Qdrant] ef={ef}, recall@{CONF['topk']}={recall:.3f}")
        
        # Add ef and recall to results
        for r in results:
            r["ef"] = ef
            r["recall"] = recall
        
        all_results.extend(results)
        
        return all_results
    else:
        # Normal benchmark with fixed ef and latency tracking
        def search_callable(qs, secs, conc):
            from concurrent.futures import ThreadPoolExecutor, as_completed
            stop_at = time.time() + secs
            chunks = np.array_split(qs, conc)
            all_latencies = []
            
            def worker(batch):
                done = 0
                worker_latencies = []
                while time.time() < stop_at:
                    t_start = time.time()
                    _ = qc.search(conn, "bench", batch, CONF["topk"], ef_search=64)
                    t_end = time.time()
                    worker_latencies.append(t_end - t_start)
                    done += len(batch)
                return done, worker_latencies
                
            total = 0
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = [ex.submit(worker, b) for b in chunks if len(b) > 0]
                for fu in as_completed(futs):
                    worker_total, worker_latencies = fu.result()
                    total += worker_total
                    all_latencies.extend(worker_latencies)
            
            return total / float(secs), all_latencies

        results = run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable,
                                       budget_s=ARGS.budget_s, disable_monitor=ARGS.no_monitor)

        # Recall@k cepat (subset 64)
        res_idx = qc.search(conn, "bench", queries[:min(64, gt_q)], CONF["topk"], ef_search=64)
        recall = recall_at_k(gt_idx[:min(64, gt_q)], res_idx)
        log(f"[Qdrant] recall@{CONF['topk']}={recall:.3f}")
        
        # Add recall to results
        for r in results:
            r["recall"] = recall
            
        return results
def run_weaviate(ds, vec_override=None, qry_override=None):
    wh = WeaviateClient()
    conn = wh.connect()

    # Load dataset
    from datasets import make_or_load_dataset
    vectors, queries, *_ = make_or_load_dataset(
        root=CONF.get("data_root", "../datasets"),
        name=ds["name"],
        n=ds["n_vectors"],
        dim=ds["dim"],
        n_queries=ds["n_queries"],
        seed=CONF.get("seed", 42),
        pdf_dir=CONF.get("pdf_dir") or "",
        embedder=CONF.get("embedder", "sentence-transformers"),
        enable_payload=CONF.get("enable_payload_filter", False),
        enable_hybrid=CONF.get("enable_hybrid_search", False),
    )
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override

    wh.drop_recreate(conn, "BenchClass", ds["dim"], "cosine")
    wh.insert(conn, "BenchClass", vectors, texts=None)
    time.sleep(1)

    gt_q  = int(CONF.get("gt_queries_for_recall", 128))
    gt_idx = brute_force_topk(vectors, queries[:gt_q], CONF["topk"], metric="COSINE")

    # Sensitivity study: test different ef values
    if ARGS.sensitivity:
        ef_values = [64, 128, 192, 256]
        all_results = []
        
        for ef in ef_values:
            log(f"[Weaviate] Testing ef={ef}")
            
            # For Weaviate, we need to recreate the collection with the new ef value
            # since Weaviate sets ef at the class level, not per search
            wh.drop_recreate(conn, "BenchClass", ds["dim"], "cosine", ef=ef)
            wh.insert(conn, "BenchClass", vectors, texts=None)
            time.sleep(1)  # Allow indexing to complete
            
            def search_callable(qs, secs, conc):
                from concurrent.futures import ThreadPoolExecutor, as_completed
                stop_at = time.time() + secs
                chunks = np.array_split(qs, conc)
                all_latencies = []
                
                def worker(batch):
                    done = 0
                    worker_latencies = []
                    while time.time() < stop_at:
                        t_start = time.time()
                        _ = wh.search(conn, "BenchClass", batch, CONF["topk"], ef=ef, hybrid=False)
                        t_end = time.time()
                        worker_latencies.append(t_end - t_start)
                        done += len(batch)
                    return done, worker_latencies
                    
                total = 0
                with ThreadPoolExecutor(max_workers=conc) as ex:
                    futs = [ex.submit(worker, b) for b in chunks if len(b) > 0]
                    for fu in as_completed(futs):
                        worker_total, worker_latencies = fu.result()
                        total += worker_total
                        all_latencies.extend(worker_latencies)
                
                return total / float(secs), all_latencies

            results = run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable,
                                           budget_s=ARGS.budget_s, disable_monitor=ARGS.no_monitor)

            # Calculate recall for this ef
            res_idx = wh.search(conn, "BenchClass", queries[:min(64, gt_q)], CONF["topk"], ef=ef, hybrid=False)
            recall = recall_at_k(gt_idx[:min(64, gt_q)], res_idx)
            log(f"[Weaviate] ef={ef}, recall@{CONF['topk']}={recall:.3f}")
            
            # Add ef and recall to results
            for r in results:
                r["ef"] = ef
                r["recall"] = recall
            
            all_results.extend(results)
        
        return all_results
    else:
        # Normal benchmark with latency tracking
        def search_callable(qs, secs, conc):
            from concurrent.futures import ThreadPoolExecutor, as_completed
            stop_at = time.time() + secs
            chunks = np.array_split(qs, conc)
            all_latencies = []
            
            def worker(batch):
                done = 0
                worker_latencies = []
                while time.time() < stop_at:
                    t_start = time.time()
                    _ = wh.search(conn, "BenchClass", batch, CONF["topk"], ef=64, hybrid=False)
                    t_end = time.time()
                    worker_latencies.append(t_end - t_start)
                    done += len(batch)
                return done, worker_latencies
                
            total = 0
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = [ex.submit(worker, b) for b in chunks if len(b) > 0]
                for fu in as_completed(futs):
                    worker_total, worker_latencies = fu.result()
                    total += worker_total
                    all_latencies.extend(worker_latencies)
            
            return total / float(secs), all_latencies

        results = run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable,
                                       budget_s=ARGS.budget_s, disable_monitor=ARGS.no_monitor)

        res_idx = wh.search(conn, "BenchClass", queries[:min(64, gt_q)], CONF["topk"], ef=64, hybrid=False)
        recall = recall_at_k(gt_idx[:min(64, gt_q)], res_idx)
        log(f"[Weaviate] recall@{CONF['topk']}={recall:.3f}")
        
        # Add recall to results
        for r in results:
            r["recall"] = recall
            
        return results


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fast benchmark for Qdrant vs Weaviate (≤5 min mode)")
    ap.add_argument("--db", choices=["qdrant", "weaviate"], help="Database backend")
    ap.add_argument("--index", default="hnsw")
    ap.add_argument("--dataset", help="Dataset name from config.yaml")
    ap.add_argument("--budget_s", type=int, default=300, help="Wall-clock limit (sec)")
    ap.add_argument("--quick5", action="store_true", help="Force ≤5 min profile")  # ← ADD
    ap.add_argument("--limit_n", type=int, help="Use only first N vectors")
    ap.add_argument("--no_monitor", action="store_true", help="Disable I/O monitor for speed")
    ap.add_argument("--sensitivity", action="store_true", help="Run sensitivity study (test different ef values)")
    args = ap.parse_args()
    ARGS = args

    import yaml
    with open("config.yaml", "r") as f:
        CONF = yaml.safe_load(f)

    if args.quick5:
        CONF["concurrency_grid"] = [1]
        CONF["repeats"] = min(CONF.get("repeats", 5), 3)
        CONF["run_seconds"] = min(CONF.get("run_seconds", 10), 8)
        # batasi ef agar tuning tidak melebar
        CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_start"] = 64
        CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_max"]   = 128
        CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_start"] = 64
        CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_max"]   = 128

    ds = next(d for d in CONF["datasets"] if d["name"] == args.dataset)
    
    # Load dataset using make_or_load_dataset function
    from datasets import make_or_load_dataset
    vectors, queries, metadata, vectors_sparse, queries_sparse = make_or_load_dataset(
        root=CONF.get("data_root", "../datasets"),
        name=ds["name"],
        n=ds["n_vectors"],
        dim=ds["dim"],
        n_queries=ds["n_queries"],
        seed=CONF.get("seed", 42),
        pdf_dir=CONF.get("pdf_dir") or "",
        embedder=CONF.get("embedder", "sentence-transformers"),
        enable_payload=CONF.get("enable_payload_filter", False),
        enable_hybrid=CONF.get("enable_hybrid_search", False),
    )

    if args.limit_n:
        vectors = vectors[:min(len(vectors), args.limit_n)]

    if args.db == "qdrant":
        out = run_qdrant(ds, vectors, queries)
    elif args.db == "weaviate":
        out = run_weaviate(ds, vectors, queries)
    else:
        raise SystemExit("Please specify --db qdrant|weaviate")

    os.makedirs("results", exist_ok=True)
    sensitivity_suffix = "_sensitivity" if ARGS.sensitivity else ""
    out_path = (
        f"results/{args.db}_{args.dataset}{sensitivity_suffix}_quick.json"
        if args.quick5 else
        f"results/{args.db}_{args.dataset}{sensitivity_suffix}.json"
    )
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)


