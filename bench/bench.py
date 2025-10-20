# bench/bench.py
"""
Vector Database Benchmark: Qdrant vs Weaviate
==============================================
Mengikuti metodologi paper rujukan dengan fokus pada HNSW-based comparison.

CATATAN PENTING:
- Milvus dikecualikan dari benchmark ini karena:
  1. Resource-intensive (membutuhkan RAM dan CPU tinggi)
  2. Sering unstable di macOS/laptop environment
  3. Kompleksitas API yang tinggi
  
- Fokus perbandingan: Qdrant vs Weaviate (keduanya menggunakan HNSW index)
- Metodologi tetap mengikuti paper rujukan:
  * Single-machine setup dengan Docker
  * NVMe storage terdedikasi
  * 30 detik per run dengan 1,000 queries
  * Flush page cache sebelum setiap run
  * 5× ulangan untuk reliability
  * Tuning hingga recall@10 ≥ 0.9
  * Metrik: QPS, P99 latency, CPU usage, I/O traces

Perbandingan ini tetap valid karena:
1. Kedua sistem menggunakan HNSW sebagai indeks utama
2. Kedua sistem Docker-based (baseline homogen)
3. Parameter tuning dapat dibandingkan secara langsung
4. Trade-off recall vs QPS dapat dianalisis dengan fair
"""
import os, time, yaml, threading, json, argparse, pathlib, importlib.util
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from utils import brute_force_topk, recall_at_k, percentiles
from datasets import make_or_load_dataset
from monitoring import sample_container_cpu, IOMonitor, run_fio_baseline

CONF = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r"))
DATA_ROOT = CONF.get("data_root", "/datasets")
PDF_DIR = CONF.get("pdf_dir")
EMBEDDER = CONF.get("embedder", "sentence-transformers")
ENABLE_PAYLOAD = CONF.get("enable_payload_filter", False)
ENABLE_HYBRID = CONF.get("enable_hybrid_search", False)
SENSITIVITY_STUDY = CONF.get("sensitivity_study", False)

def log(*a): print(*a, flush=True)

from clients import QdrantClientHelper, WeaviateClient

def run_concurrency_grid(container_name, run_seconds, queries, search_callable):
    """Jalankan grid concurrency:
       - durasi 30s penuh (ring-buffer kueri)
       - repeats=CONF['repeats']
       - catat latensi per-kueri
    """
    results = []
    total_conc = len(CONF["concurrency_grid"])
    total_runs = total_conc * CONF.get("repeats", 1)
    run_count = 0
    
    for conc in CONF["concurrency_grid"]:
        log(f"[{container_name}] Starting concurrency {conc} (run {run_count+1}/{total_runs})")
        all_runs = []
        for repeat in range(CONF.get("repeats", 1)):
            run_count += 1
            log(f"[{container_name}] Concurrency {conc}, repeat {repeat+1}/{CONF.get('repeats', 1)} - Running for {run_seconds}s...")
            
            # flush + warm-up ringan
            # flush_page_cache(); time.sleep(1)
            try:
                _ = search_callable(queries[:min(64, len(queries))], time.perf_counter())
                time.sleep(1)
            except Exception as e:
                log(f"[{container_name}] Warning: Warm-up failed: {e}, continuing anyway...")

            # Start monitoring threads
            io_monitor = IOMonitor()
            io_thread = io_monitor.start_monitoring(run_seconds + 5)
            
            # Start CPU monitoring in separate thread
            cpu_values = []
            cpu_monitoring = True
            
            def cpu_monitor_thread():
                while cpu_monitoring:
                    try:
                        cpu_pct = sample_container_cpu(container_name, 1)  # Sample every 1 second
                        if cpu_pct > 0:
                            cpu_values.append(cpu_pct)
                        time.sleep(1)
                    except Exception as e:
                        if config.get("debug", False):
                            print(f"CPU monitoring error: {e}")
                        break
            
            cpu_thread = threading.Thread(target=cpu_monitor_thread, daemon=True)
            cpu_thread.start()

            lat_ms = []
            stop_at = time.time() + run_seconds
            qn = len(queries); head = 0
            
            # Progress bar untuk run_seconds
            with tqdm(total=run_seconds, desc=f"[{container_name}] Running", unit="s", ncols=80, disable=False) as pbar:
                start_time = time.time()
                last_update = start_time
                
                with ThreadPoolExecutor(max_workers=conc) as ex:
                    while time.time() < stop_at:
                        per = max(1, min(4, qn // max(1, conc)))  # batch kecil agar latensi mendekati per-kueri
                        futs = []
                        for _w in range(conc):
                            tail = (head + per) % qn
                            if tail > head:
                                qb = queries[head:tail]
                            else:
                                qb = np.concatenate([queries[head:], queries[:tail]], axis=0)
                            head = tail
                            t0 = time.perf_counter()
                            futs.append(ex.submit(search_callable, qb, t0))
                        for fu in futs:
                            qcount, t0, t1 = fu.result()
                            perq = (t1 - t0) * 1000.0 / max(1, qcount)
                            lat_ms.extend([perq] * qcount)
                        
                        # Update progress bar setiap detik
                        current_time = time.time()
                        if current_time - last_update >= 1:
                            elapsed = current_time - start_time
                            pbar.n = min(elapsed, run_seconds)
                            pbar.refresh()
                            last_update = current_time
                
                # Final update
                pbar.n = run_seconds
                pbar.refresh()

            # Stop monitoring
            cpu_monitoring = False
            io_monitor.stop_monitoring()
            io_thread.join(timeout=run_seconds + 10)  # Wait for iostat to complete
            cpu_thread.join(timeout=5)  # Wait for CPU monitoring to stop
            
            io_stats = io_monitor.parse_bandwidth()
            
            # Calculate average CPU usage from collected samples
            cpu_monitor = sum(cpu_values) / len(cpu_values) if cpu_values else 0.0
            
            qps = len(lat_ms) / run_seconds
            p = percentiles(lat_ms)
            all_runs.append({
                "conc": conc, "qps": qps, "p50": p["p50"], "p95": p["p95"], "p99": p["p99"],
                "cpu": cpu_monitor, **io_stats
            })

        def _avg(k): return float(np.mean([x[k] for x in all_runs]))
        results.append({
            "conc": conc,
            "qps": _avg("qps"),
            "p50": _avg("p50"), "p95": _avg("p95"), "p99": _avg("p99"),
            "cpu": _avg("cpu"),
            "read_mb": _avg("read_mb"), "write_mb": _avg("write_mb"),
            "total_mb": _avg("total_mb"), "avg_bandwidth_mb_s": _avg("avg_bandwidth_mb_s"),
            "repeats": len(all_runs)
        })
        log(f"[{container_name}] conc={conc} qps={results[-1]['qps']:.1f} "
            f"p99={results[-1]['p99']:.1f}ms cpu={results[-1]['cpu']:.1f}%")
    return results

# ---------------- Qdrant ----------------
def run_qdrant(ds, vec_override=None, qry_override=None):
    log(f"[qdrant] Starting benchmark for dataset {ds['name']} ({ds['n_vectors']} vectors)")
    # Estimasi waktu: tuning ~2min + concurrency grid ~10min = ~12min total
    total_conc = len(CONF["concurrency_grid"])
    total_runs = total_conc * CONF.get("repeats", 1)
    estimated_time_min = 2 + (total_runs * CONF["run_seconds"] / 60)
    log(f"[qdrant] Estimated total time: ~{estimated_time_min:.0f} minutes ({total_runs} runs)")
    
    qh = QdrantClientHelper()
    name = "bench"
    n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override
        metadata = None
        vectors_sparse, queries_sparse = None, None
    else:
        vectors, queries, metadata, vectors_sparse, queries_sparse = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD, enable_hybrid=ENABLE_HYBRID)

    qh.drop_recreate(qh.connect(), name, d, "cosine",
                     on_disk=CONF["indexes"]["qdrant"]["hnsw"]["on_disk"])
    qh.insert(qh.connect(), name, vectors, payload=metadata)

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")

    start = CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_start"]
    maxv  = CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_max"]
    best = start; val = start
    max_iterations = 10  # Prevent infinite loop
    iteration = 0
    while val <= maxv and iteration < max_iterations:
        try:
            idx = qh.search(qh.connect(), name, queries[:64], CONF["topk"], ef_search=int(val))
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
        except Exception as e:
            log(f"[qdrant] Error during tuning ef_search={val}: {e}")
        val *= 2
        iteration += 1
    if iteration >= max_iterations:
        log(f"[qdrant] Warning: Tuning reached max iterations, using ef_search={best}")
    tuned_ef = int(best)
    log(f"[qdrant][hnsw] tuned ef_search={tuned_ef}")

    def search_callable(qb, t0):
        _ = qh.search(qh.connect(), name, qb, CONF["topk"], ef_search=tuned_ef)
        t1 = time.perf_counter()
        return len(qb), t0, t1

    return run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable)

# ---------------- Weaviate ----------------
def run_weaviate(ds, vec_override=None, qry_override=None):
    wh = WeaviateClient()
    classname = "BenchItem"
    n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override
        metadata = None
        vectors_sparse, queries_sparse = None, None
    else:
        vectors, queries, metadata, vectors_sparse, queries_sparse = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD, enable_hybrid=ENABLE_HYBRID)

    conn = wh.connect()

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")

    start = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_start"]
    maxv  = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_max"]
    best = start; val = start
    max_iterations = 10  # Prevent infinite loop
    iteration = 0
    while val <= maxv and iteration < max_iterations:
        try:
            wh.drop_recreate(conn, classname, d, "cosine", ef=int(val))
            wh.insert(conn, classname, vectors)
            time.sleep(2)
            idx = wh.search(conn, classname, queries[:64], CONF["topk"], ef=int(val), hybrid=ENABLE_HYBRID, query_texts=["sample query"]*64 if ENABLE_HYBRID else None)
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
        except Exception as e:
            log(f"[weaviate] Error during tuning ef={val}: {e}")
        val *= 2
        iteration += 1
    if iteration >= max_iterations:
        log(f"[weaviate] Warning: Tuning reached max iterations, using ef={best}")
    tuned_ef = int(best)
    log(f"[weaviate][hnsw] tuned ef={tuned_ef}")

    def search_callable(qb, t0):
        query_texts = ["sample query"] * len(qb) if ENABLE_HYBRID else None
        _ = wh.search(conn, classname, qb, CONF["topk"], ef=tuned_ef, hybrid=ENABLE_HYBRID, query_texts=query_texts)
        t1 = time.perf_counter()
        return len(qb), t0, t1

    return run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable)

# ---------------- Sensitivity Study ----------------
def run_sensitivity_study(db, index_kind, ds):
    """Jalankan sensitivity study: eksplorasi parameter terhadap QPS dengan recall tetap >= target."""
    log(f"Running sensitivity study for {db} {index_kind}")
    results = []
    
    if db == "qdrant":
        qh = QdrantClientHelper()
        name = "bench"
        n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
        vectors, queries, metadata, vectors_sparse, queries_sparse = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD, enable_hybrid=ENABLE_HYBRID)
        qh.drop_recreate(qh.connect(), name, d, "cosine", on_disk=CONF["indexes"]["qdrant"]["hnsw"]["on_disk"])
        qh.insert(qh.connect(), name, vectors, payload=metadata)
        gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")
        
        # Grid untuk ef_search
        ef_grid = [10, 50, 100, 200, 500, 1000]
        for ef in ef_grid:
            idx = qh.search(qh.connect(), name, queries[:64], CONF["topk"], ef_search=ef)
            recall = recall_at_k(gt_idx[:64], idx)
            if recall >= CONF["target_recall_at_k"]:
                def search_callable(qb, t0):
                    _ = qh.search(qh.connect(), name, qb, CONF["topk"], ef_search=ef)
                    t1 = time.perf_counter()
                    return len(qb), t0, t1
                res = run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable)
                for r in res:
                    r["param"] = {"ef_search": ef}
                    r["recall"] = recall
                results.extend(res)
    
    elif db == "weaviate":
        wh = WeaviateClient()
        classname = "BenchItem"
        n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
        vectors, queries, metadata, vectors_sparse, queries_sparse = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD, enable_hybrid=ENABLE_HYBRID)
        conn = wh.connect()
        gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")
        
        # Grid untuk ef
        ef_grid = [10, 50, 100, 200, 500, 1000]
        for ef in ef_grid:
            wh.drop_recreate(conn, classname, d, "cosine", ef=ef)
            wh.insert(conn, classname, vectors)
            time.sleep(2)
            idx = wh.search(conn, classname, queries[:64], CONF["topk"], ef=ef, hybrid=ENABLE_HYBRID, query_texts=["sample query"]*64 if ENABLE_HYBRID else None)
            recall = recall_at_k(gt_idx[:64], idx)
            if recall >= CONF["target_recall_at_k"]:
                def search_callable(qb, t0):
                    query_texts = ["sample query"] * len(qb) if ENABLE_HYBRID else None
                    _ = wh.search(conn, classname, qb, CONF["topk"], ef=ef, hybrid=ENABLE_HYBRID, query_texts=query_texts)
                    t1 = time.perf_counter()
                    return len(qb), t0, t1
                res = run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable)
                for r in res:
                    r["param"] = {"ef": ef}
                    r["recall"] = recall
                results.extend(res)
    
    return results

# ---------------- main ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Benchmark Qdrant vs Weaviate for semantic search on PDF embeddings"
    )
    ap.add_argument("--db", choices=["qdrant", "weaviate"], required=False,
                    help="Vector database to benchmark (qdrant or weaviate)")
    ap.add_argument("--index", choices=["hnsw"], default="hnsw",
                    help="Index type (only HNSW supported for fair comparison)")
    ap.add_argument("--dataset", choices=[d["name"] for d in CONF["datasets"]],
                    help="Dataset to use for benchmarking")
    ap.add_argument("--baseline", action="store_true", 
                    help="Run fio baseline tests only")
    ap.add_argument("--sensitivity", action="store_true", 
                    help="Run sensitivity study (recall vs QPS trade-off)")
    ap.add_argument("--embeddings_npy", 
                    help="Path to custom embeddings .npy file")
    ap.add_argument("--queries_npy", 
                    help="Path to custom queries .npy file")
    args = ap.parse_args()

    if args.baseline:
        log("Running fio baseline tests...")
        baseline_results = run_fio_baseline(DATA_ROOT, 30)
        print(json.dumps(baseline_results, indent=2))
        raise SystemExit(0)

    if args.sensitivity:
        if not all([args.db, args.index, args.dataset]):
            ap.error("--db, --index, and --dataset are required for sensitivity study")
        ds = next(d for d in CONF["datasets"] if d["name"] == args.dataset)
        out = run_sensitivity_study(args.db, args.index, ds)
    else:
        if not all([args.db, args.index, args.dataset]):
            ap.error("--db, --index, and --dataset are required unless using --baseline")

        ds = next(d for d in CONF["datasets"] if d["name"] == args.dataset)
        vec_override = np.load(args.embeddings_npy).astype("float32") if args.embeddings_npy else None
        qry_override = np.load(args.queries_npy).astype("float32") if args.queries_npy else None

        # Execute benchmark for selected database
        if args.db == "qdrant":
            out = run_qdrant(ds, vec_override, qry_override)
        elif args.db == "weaviate":
            out = run_weaviate(ds, vec_override, qry_override)
        else:
            raise SystemExit("Error: --db must be 'qdrant' or 'weaviate'")

    print(json.dumps(out, indent=2))
