# /bench/datasets.py
import os, numpy as np, pathlib

rng = np.random.default_rng

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def make_or_load_dataset(root, name, n, dim, n_queries, seed=42):
    """Load or generate synthetic dataset for benchmarking."""
    droot = os.path.join(root, name)
    ensure_dir(droot)
    vec_path = os.path.join(droot, "vectors.npy")
    qry_path = os.path.join(droot, "queries.npy")

    if not (os.path.exists(vec_path) and os.path.exists(qry_path)):
        print("Generating synthetic dataset")
        r = rng(seed)
        vectors = r.normal(0.0, 1.0, size=(n, dim)).astype("float32")
        queries = r.normal(0.0, 1.0, size=(n_queries, dim)).astype("float32")
        np.save(vec_path, vectors)
        np.save(qry_path, queries)
    else:
        vectors = np.load(vec_path)
        queries = np.load(qry_path)

    return vectors, queries
