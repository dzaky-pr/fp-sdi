import os, numpy as np, pathlib, json
rng = np.random.default_rng

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def make_or_load_dataset(root, name, n, dim, n_queries, seed=42):
    droot = os.path.join(root, name)
    ensure_dir(droot)
    vec_path = os.path.join(droot, "vectors.npy")
    qry_path = os.path.join(droot, "queries.npy")

    if not (os.path.exists(vec_path) and os.path.exists(qry_path)):
        r = rng(seed)
        # Synthetic Gaussian with mild anisotropy to mimic real-ish distribution
        vectors = r.normal(loc=0.0, scale=1.0, size=(n, dim)).astype("float32")
        queries = r.normal(loc=0.0, scale=1.0, size=(n_queries, dim)).astype("float32")
        np.save(vec_path, vectors); np.save(qry_path, queries)
    else:
        vectors = np.load(vec_path); queries = np.load(qry_path)
    return vectors, queries
