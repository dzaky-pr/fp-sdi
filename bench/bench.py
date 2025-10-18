import os, time, yaml, threading, json
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from utils import brute_force_topk, recall_at_k, percentiles, flush_page_cache
from datasets import make_or_load_dataset
from cpu_dockerstats import sample_container_cpu
from io_monitor import IOMonitor, run_fio_baseline
import importlib.util, pathlib

CONF = yaml.safe_load(open("config.yaml","r"))
DATA_ROOT = os.environ.get("DATA_ROOT", "/datasets")

def log(*a): print(*a, flush=True)

def _import_helper(fname: str, asname: str):
    p = pathlib.Path(__file__).parent / fname
    spec = importlib.util.spec_from_file_location(asname, p.as_posix())
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def run_concurrency_grid(container_name, run_seconds, queries, search_callable):
    results = []
    for conc in CONF["concurrency_grid"]:
        log(f"[{container_name}] Starting concurrency {conc}")
        
        # Flush page cache before each run
        flush_page_cache()
        time.sleep(1)  # Allow cache flush to complete
        
        # Start I/O monitoring
        io_monitor = IOMonitor()
        io_thread = io_monitor.start_monitoring(run_seconds + 5)
        
        lat_ms, done = [], 0
        stop_at = time.time() + run_seconds

        cpu_box = [0.0]
        t_cpu = threading.Thread(target=lambda: cpu_box.__setitem__(0, sample_container_cpu(container_name, run_seconds)),
                                 daemon=True)
        t_cpu.start()

        while time.time() < stop_at and done < len(queries):
            per = max(1, len(queries) // max(1, conc))
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = []
                for t in range(conc):
                    qb = queries[(done + t*per):(done + (t+1)*per)]
                    if qb.size == 0: continue
                    t0 = time.perf_counter()
                    fut = ex.submit(search_callable, qb); fut.t0 = t0
                    futs.append(fut)
                for fu in futs:
                    _ = fu.result()
                    lat_ms.append((time.perf_counter() - fu.t0)*1000.0)
            done += per * conc

        # Stop monitoring and collect results
        io_monitor.stop_monitoring()
        io_thread.join(timeout=2)
        io_results = io_monitor.get_results()
        bandwidth_stats = io_monitor.parse_bandwidth()

        p = percentiles(lat_ms)
        qps = done / run_seconds
        t_cpu.join(timeout=0.1)
        
        result = {
            "conc": conc, 
            "qps": qps, 
            "p50": p["p50"], 
            "p95": p["p95"], 
            "p99": p["p99"], 
            "cpu": cpu_box[0],
            "io_bandwidth_mb": bandwidth_stats.get("total_mb", 0),
            "io_read_mb": bandwidth_stats.get("read_mb", 0),
            "io_write_mb": bandwidth_stats.get("write_mb", 0),
            "avg_bandwidth_mb_s": bandwidth_stats.get("avg_bandwidth_mb_s", 0)
        }
        
        results.append(result)
        log(f"[{container_name}] conc={conc} qps={qps:.1f} p99={p['p99']:.1f}ms cpu={cpu_box[0]:.1f}% io_read={bandwidth_stats.get('read_mb', 0):.1f}MB")
    return results

# ---------------- Milvus ----------------
def run_milvus(index_kind, ds):
    from milvus_client import connect, insert_and_flush, run_build, search as milvus_search
    c = connect()
    n,d,nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    vectors, queries = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"])

    metric = CONF["indexes"]["milvus"][index_kind]["metric"]
    build_cfg = CONF["indexes"]["milvus"][index_kind]["build"]
    log("[milvus] recreate+build:", index_kind)
    run_build(c, index_kind, n, d, metric, build_cfg)
    insert_and_flush(c, vectors)

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric=("IP" if metric.upper()=="IP" else "COSINE"))

    if index_kind == "ivf":
        start = CONF["indexes"]["milvus"]["ivf"]["search"]["nprobe_start"]
        maxv  = CONF["indexes"]["milvus"]["ivf"]["search"]["nprobe_max"]
        best = start
        val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"nprobe": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val *= 2
        param = {"nprobe": int(best)}
        log(f"[milvus][ivf] tuned nprobe={best}")

        def search_callable(qb):
            return c.search("bench", data=qb.tolist(), anns_field="vec", limit=CONF["topk"], params=param)

    elif index_kind == "hnsw":
        start = CONF["indexes"]["milvus"]["hnsw"]["search"]["efSearch_start"]
        maxv  = CONF["indexes"]["milvus"]["hnsw"]["search"]["efSearch_max"]
        best = start
        val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"ef": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val *= 2
        param = {"ef": int(best)}
        log(f"[milvus][hnsw] tuned ef={best}")

        def search_callable(qb):
            return c.search("bench", data=qb.tolist(), anns_field="vec", limit=CONF["topk"], params=param)

    else:  # diskann
        start = CONF["indexes"]["milvus"]["diskann"]["search"]["search_list_start"]
        maxv  = CONF["indexes"]["milvus"]["diskann"]["search"]["search_list_max"]
        best = start
        val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"search_list": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val += 10
        param = {"search_list": int(best)}
        log(f"[milvus][diskann] tuned search_list={best}")

        def search_callable(qb):
            return c.search("bench", data=qb.tolist(), anns_field="vec", limit=CONF["topk"], params=param)

    return run_concurrency_grid("milvus", CONF["run_seconds"], queries, search_callable)

# ---------------- Qdrant ----------------
def run_qdrant(ds):
    qh = _import_helper("qdrant_helper.py", "qh")
    name="bench"
    n,d,nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    vectors, queries = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"])

    qh.drop_recreate(qh.connect(), name, d, "cosine",
                     on_disk=CONF["indexes"]["qdrant"]["hnsw"]["on_disk"])
    qh.insert(qh.connect(), name, vectors)

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")

    start = CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_start"]
    maxv  = CONF["indexes"]["qdrant"]["hnsw"]["search"]["ef_search_max"]
    best = start; val = start
    while val <= maxv:
        idx = qh.search(qh.connect(), name, queries[:64], CONF["topk"], ef_search=int(val))
        if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
            best = val; break
        val *= 2
    tuned_ef = int(best)
    log(f"[qdrant][hnsw] tuned ef_search={tuned_ef}")

    def search_callable(qb):
        return qh.search(qh.connect(), name, qb, CONF["topk"], ef_search=tuned_ef)

    return run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable)

# ---------------- Weaviate ----------------
def run_weaviate(ds):
    wh = _import_helper("weaviate_client.py", "wh")
    classname="BenchItem"
    n,d,nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    vectors, queries = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"])

    wh.drop_recreate(wh.connect(), classname, d, "cosine")
    wh.insert(wh.connect(), classname, vectors)
    time.sleep(2)

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")

    start = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_start"]
    maxv  = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_max"]
    best = start; val = start
    while val <= maxv:
        idx = wh.search(wh.connect(), classname, queries[:64], CONF["topk"], ef=int(val))
        if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
            best = val; break
        val *= 2
    tuned_ef = int(best)
    log(f"[weaviate][hnsw] tuned ef={tuned_ef}")

    def search_callable(qb):
        return wh.search(wh.connect(), classname, qb, CONF["topk"], ef=tuned_ef)

    return run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable)

# ---------------- main ----------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=["milvus","qdrant","weaviate"])
    ap.add_argument("--index", choices=["ivf","hnsw","diskann"])
    ap.add_argument("--dataset", choices=[d["name"] for d in CONF["datasets"]])
    ap.add_argument("--baseline", action="store_true", help="Run fio baseline tests only")
    args = ap.parse_args()

    if args.baseline:
        log("Running fio baseline tests...")
        baseline_results = run_fio_baseline(DATA_ROOT, 30)
        print(json.dumps(baseline_results, indent=2))
        exit(0)

    if not all([args.db, args.index, args.dataset]):
        ap.error("--db, --index, and --dataset are required unless using --baseline")

    ds = next(d for d in CONF["datasets"] if d["name"]==args.dataset)

    if args.db != "milvus" and args.index != "hnsw":
        raise SystemExit("Qdrant/Weaviate: gunakan --index hnsw.")

    if args.db == "milvus":
        out = run_milvus(args.index, ds)
    elif args.db == "qdrant":
        out = run_qdrant(ds)
    else:
        out = run_weaviate(ds)

    print(json.dumps(out, indent=2))
