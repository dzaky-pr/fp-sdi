# bench/bench.py
import os, time, yaml, threading, json, argparse, pathlib, importlib.util
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from utils import brute_force_topk, recall_at_k, percentiles, flush_page_cache
from datasets import make_or_load_dataset
from cpu_dockerstats import sample_container_cpu
from io_monitor import IOMonitor, run_fio_baseline

CONF = yaml.safe_load(open("config.yaml", "r"))
DATA_ROOT = os.environ.get("DATA_ROOT", "/datasets")
PDF_DIR = CONF.get("pdf_dir")
EMBEDDER = CONF.get("embedder", "sentence-transformers")
ENABLE_PAYLOAD = CONF.get("enable_payload_filter", False)
ENABLE_HYBRID = CONF.get("enable_hybrid_search", False)
SENSITIVITY_STUDY = CONF.get("sensitivity_study", False)

def log(*a): print(*a, flush=True)

def _import_helper(fname: str, asname: str):
    p = pathlib.Path(__file__).parent / fname
    spec = importlib.util.spec_from_file_location(asname, p.as_posix())
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_concurrency_grid(container_name, run_seconds, queries, search_callable):
    """Jalankan grid concurrency:
       - durasi 30s penuh (ring-buffer kueri)
       - repeats=CONF['repeats']
       - catat latensi per-kueri
    """
    results = []
    for conc in CONF["concurrency_grid"]:
        all_runs = []
        for _ in range(CONF.get("repeats", 1)):
            # flush + warm-up ringan
            flush_page_cache(); time.sleep(1)
            try:
                _ = search_callable(queries[:min(64, len(queries))], time.perf_counter())
                time.sleep(1)
            except Exception:
                pass

            io_monitor = IOMonitor()
            io_thread = io_monitor.start_monitoring(run_seconds + 5)

            lat_ms = []
            stop_at = time.time() + run_seconds
            qn = len(queries); head = 0

            cpu_box = [0.0]
            t_cpu = threading.Thread(
                target=lambda: cpu_box.__setitem__(0, sample_container_cpu(container_name, run_seconds)),
                daemon=True
            )
            t_cpu.start()

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

            io_monitor.stop_monitoring(); io_thread.join(timeout=2)
            io_stats = io_monitor.parse_bandwidth()
            t_cpu.join(timeout=0.1)

            qps = len(lat_ms) / run_seconds
            p = percentiles(lat_ms)
            all_runs.append({
                "conc": conc, "qps": qps, "p50": p["p50"], "p95": p["p95"], "p99": p["p99"],
                "cpu": cpu_box[0], **io_stats
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

# ---------------- Milvus ----------------
def run_milvus(index_kind, ds, vec_override=None, qry_override=None):
    from milvus_client import (
        connect, drop_recreate, insert_and_flush,
        build_index_ivf, build_index_hnsw, build_index_diskann,
        wait_index_ready, load_collection, search as milvus_search, _nlist_rule,
    )
    c = connect()
    n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override
        metadata = None
    else:
        vectors, queries, metadata = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD)

    metric = CONF["indexes"]["milvus"][index_kind]["metric"]
    build_cfg = CONF["indexes"]["milvus"][index_kind]["build"]

    log("[milvus] recreate collection")
    drop_recreate(c, d, metric)
    insert_and_flush(c, vectors)

    if index_kind == "ivf":
        nlist = build_cfg.get("nlist") or _nlist_rule(len(vectors))
        build_index_ivf(c, len(vectors), metric, nlist)
    elif index_kind == "hnsw":
        build_index_hnsw(c, metric, build_cfg["M"], build_cfg["efConstruction"])
    else:
        build_index_diskann(c, metric)

    wait_index_ready(c)
    load_collection(c, "bench")

    gt_idx = brute_force_topk(
        vectors, queries, CONF["topk"],
        metric=("IP" if metric.upper() == "IP" else "COSINE")
    )

    if index_kind == "ivf":
        start = CONF["indexes"]["milvus"]["ivf"]["search"]["nprobe_start"]
        maxv  = CONF["indexes"]["milvus"]["ivf"]["search"]["nprobe_max"]
        best = start; val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"nprobe": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val *= 2
        param = {"nprobe": int(best)}
        log(f"[milvus][ivf] tuned nprobe={best}")

    elif index_kind == "hnsw":
        start = CONF["indexes"]["milvus"]["hnsw"]["search"]["efSearch_start"]
        maxv  = CONF["indexes"]["milvus"]["hnsw"]["search"]["efSearch_max"]
        best = start; val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"ef": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val *= 2
        param = {"ef": int(best)}
        log(f"[milvus][hnsw] tuned ef={best}")

    else:  # diskann
        start = CONF["indexes"]["milvus"]["diskann"]["search"]["search_list_start"]
        maxv  = CONF["indexes"]["milvus"]["diskann"]["search"]["search_list_max"]
        best = start; val = start
        while val <= maxv:
            idx = milvus_search(c, queries[:64], CONF["topk"], {"search_list": int(val)})
            if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
                best = val; break
            val += 10
        param = {"search_list": int(best)}
        log(f"[milvus][diskann] tuned search_list={best}")

    def search_callable(qb, t0):
        _ = c.search("bench", data=qb.tolist(), anns_field="vec", limit=CONF["topk"], params=param)
        t1 = time.perf_counter()
        return len(qb), t0, t1

    return run_concurrency_grid("milvus", CONF["run_seconds"], queries, search_callable)

# ---------------- Qdrant ----------------
def run_qdrant(ds, vec_override=None, qry_override=None):
    qh = _import_helper("qdrant_helper.py", "qh")
    name = "bench"
    n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override
        metadata = None
    else:
        vectors, queries, metadata = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD)

    qh.drop_recreate(qh.connect(), name, d, "cosine",
                     on_disk=CONF["indexes"]["qdrant"]["hnsw"]["on_disk"])
    qh.insert(qh.connect(), name, vectors, payload=metadata)

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

    def search_callable(qb, t0):
        _ = qh.search(qh.connect(), name, qb, CONF["topk"], ef_search=tuned_ef)
        t1 = time.perf_counter()
        return len(qb), t0, t1

    return run_concurrency_grid("qdrant", CONF["run_seconds"], queries, search_callable)

# ---------------- Weaviate ----------------
def run_weaviate(ds, vec_override=None, qry_override=None):
    wh = _import_helper("weaviate_client.py", "wh")
    classname = "BenchItem"
    n, d, nq = ds["n_vectors"], ds["dim"], ds["n_queries"]
    if vec_override is not None and qry_override is not None:
        vectors, queries = vec_override, qry_override
        metadata = None
    else:
        vectors, queries, metadata = make_or_load_dataset(DATA_ROOT, ds["name"], n, d, nq, seed=CONF["seed"], pdf_dir=PDF_DIR, embedder=EMBEDDER, enable_payload=ENABLE_PAYLOAD)

    conn = wh.connect()

    gt_idx = brute_force_topk(vectors, queries, CONF["topk"], metric="COSINE")

    start = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_start"]
    maxv  = CONF["indexes"]["weaviate"]["hnsw"]["search"]["ef_max"]
    best = start; val = start
    while val <= maxv:
        wh.drop_recreate(conn, classname, d, "cosine", ef=int(val))
        wh.insert(conn, classname, vectors)
        time.sleep(2)
        idx = wh.search(conn, classname, queries[:64], CONF["topk"], ef=int(val), hybrid=ENABLE_HYBRID, query_texts=["sample query"]*64 if ENABLE_HYBRID else None)
        if recall_at_k(gt_idx[:64], idx) >= CONF["target_recall_at_k"]:
            best = val; break
        val *= 2
    tuned_ef = int(best)
    log(f"[weaviate][hnsw] tuned ef={tuned_ef}")

    def search_callable(qb, t0):
        query_texts = ["sample query"] * len(qb) if ENABLE_HYBRID else None
        _ = wh.search(conn, classname, qb, CONF["topk"], ef=tuned_ef, hybrid=ENABLE_HYBRID, query_texts=query_texts)
        t1 = time.perf_counter()
        return len(qb), t0, t1

    return run_concurrency_grid("weaviate", CONF["run_seconds"], queries, search_callable)

# ---------------- main ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=["milvus", "qdrant", "weaviate"])
    ap.add_argument("--index", choices=["ivf", "hnsw", "diskann"])
    ap.add_argument("--dataset", choices=[d["name"] for d in CONF["datasets"]])
    ap.add_argument("--baseline", action="store_true", help="Run fio baseline tests only")
    ap.add_argument("--embeddings_npy", help="path .npy vectors (override dataset)")
    ap.add_argument("--queries_npy", help="path .npy queries (override dataset)")
    args = ap.parse_args()

    if args.baseline:
        log("Running fio baseline tests...")
        baseline_results = run_fio_baseline(DATA_ROOT, 30)
        print(json.dumps(baseline_results, indent=2))
        raise SystemExit(0)

    if not all([args.db, args.index, args.dataset]):
        ap.error("--db, --index, and --dataset are required unless using --baseline")

    ds = next(d for d in CONF["datasets"] if d["name"] == args.dataset)
    vec_override = np.load(args.embeddings_npy).astype("float32") if args.embeddings_npy else None
    qry_override = np.load(args.queries_npy).astype("float32") if args.queries_npy else None

    if args.db != "milvus" and args.index != "hnsw":
        raise SystemExit("Qdrant/Weaviate: gunakan --index hnsw.")

    if args.db == "milvus":
        out = run_milvus(args.index, ds, vec_override, qry_override)
    elif args.db == "qdrant":
        out = run_qdrant(ds, vec_override, qry_override)
    else:
        out = run_weaviate(ds, vec_override, qry_override)

    print(json.dumps(out, indent=2))
