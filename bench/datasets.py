# bench/datasets.py
import os, numpy as np, pathlib
from pdf_embedder import generate_pdf_dataset
rng = np.random.default_rng

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def make_or_load_dataset(root, name, n, dim, n_queries, seed=42, pdf_dir=None, embedder="sentence-transformers", enable_payload=False):
    droot = os.path.join(root, name)
    ensure_dir(droot)
    vec_path = os.path.join(droot, "vectors.npy")
    qry_path = os.path.join(droot, "queries.npy")
    meta_path = os.path.join(droot, "metadata.json") if enable_payload else None
    if not (os.path.exists(vec_path) and os.path.exists(qry_path)):
        if pdf_dir and os.path.exists(pdf_dir):
            print(f"Generating dataset from PDFs in {pdf_dir}")
            vectors, queries = generate_pdf_dataset(pdf_dir, n, dim, n_queries, embedder, seed)
            if enable_payload:
                # Generate metadata (e.g., document type, page number)
                metadata = [{"doc_type": "pdf", "chunk_id": i, "source": "paper_rujukan.pdf"} for i in range(n)]
                import json
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f)
        else:
            print("Generating synthetic dataset")
            r = rng(seed)
            vectors = r.normal(0.0, 1.0, size=(n, dim)).astype("float32")
            queries = r.normal(0.0, 1.0, size=(n_queries, dim)).astype("float32")
            if enable_payload:
                metadata = [{"synthetic": True, "id": i} for i in range(n)]
                import json
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f)
        np.save(vec_path, vectors); np.save(qry_path, queries)
    else:
        vectors = np.load(vec_path); queries = np.load(qry_path)
        if enable_payload and os.path.exists(meta_path):
            import json
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = None
    return vectors, queries, metadata
