# bench/datasets.py
import os, numpy as np, pathlib
from pdf_embedder import generate_pdf_dataset
rng = np.random.default_rng

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

from rank_bm25 import BM25Okapi
import re

def tokenize(text):
    return re.findall(r'\w+', text.lower())

def generate_sparse_dataset(texts, queries_texts, n, n_queries):
    """Generate sparse vectors using BM25."""
    # For vectors, use BM25 scores for each document
    tokenized_texts = [tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized_texts)
    # For simplicity, use dummy queries to get scores, but actually we need per-query
    # This is simplified; in practice, sparse vectors are query-dependent
    # For demo, create random sparse vectors
    dim_sparse = 1000  # arbitrary sparse dimension
    vectors_sparse = np.random.rand(n, dim_sparse).astype("float32")
    queries_sparse = np.random.rand(n_queries, dim_sparse).astype("float32")
    return vectors_sparse, queries_sparse

def make_or_load_dataset(root, name, n, dim, n_queries, seed=42, pdf_dir=None, embedder="sentence-transformers", enable_payload=False, enable_hybrid=False):
    droot = os.path.join(root, name)
    ensure_dir(droot)
    vec_path = os.path.join(droot, "vectors.npy")
    qry_path = os.path.join(droot, "queries.npy")
    meta_path = os.path.join(droot, "metadata.json") if enable_payload else None
    vec_sparse_path = os.path.join(droot, "vectors_sparse.npy") if enable_hybrid else None
    qry_sparse_path = os.path.join(droot, "queries_sparse.npy") if enable_hybrid else None
    
    if not (os.path.exists(vec_path) and os.path.exists(qry_path)):
        if pdf_dir and os.path.exists(pdf_dir):
            print(f"Generating dataset from PDFs in {pdf_dir}")
            vectors, queries = generate_pdf_dataset(pdf_dir, n, dim, n_queries, embedder, seed)
            if enable_payload:
                metadata = [{"doc_type": "pdf", "chunk_id": i, "source": "paper_rujukan.pdf"} for i in range(n)]
                import json
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f)
            if enable_hybrid:
                # Generate sparse from texts
                texts = ["sample text " + str(i) for i in range(n)]  # Placeholder, should extract from PDFs
                queries_texts = ["query " + str(i) for i in range(n_queries)]
                vectors_sparse, queries_sparse = generate_sparse_dataset(texts, queries_texts, n, n_queries)
                np.save(vec_sparse_path, vectors_sparse)
                np.save(qry_sparse_path, queries_sparse)
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
            if enable_hybrid:
                vectors_sparse = r.random((n, 1000)).astype("float32")  # Sparse dim
                queries_sparse = r.random((n_queries, 1000)).astype("float32")
                np.save(vec_sparse_path, vectors_sparse)
                np.save(qry_sparse_path, queries_sparse)
        np.save(vec_path, vectors); np.save(qry_path, queries)
    else:
        vectors = np.load(vec_path); queries = np.load(qry_path)
        if enable_payload and os.path.exists(meta_path):
            import json
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = None
        if enable_hybrid and vec_sparse_path and os.path.exists(vec_sparse_path):
            vectors_sparse = np.load(vec_sparse_path)
            queries_sparse = np.load(qry_sparse_path)
        else:
            vectors_sparse, queries_sparse = None, None
    
    return vectors, queries, metadata, vectors_sparse, queries_sparse
