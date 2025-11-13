# /bench/datasets.py
import os, numpy as np, pathlib, random, PyPDF2, re
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
from rank_bm25 import BM25Okapi

rng = np.random.default_rng

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def tokenize(text):
    return re.findall(r'\w+', text.lower())

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()

def chunk_text(text: str, chunk_size: int = 512) -> list:
    """Split text into chunks for embedding."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

def embed_with_sentence_transformers(texts: list, model_name: str = "all-MiniLM-L6-v2", dim: int = 384) -> np.ndarray:
    """Embed texts using SentenceTransformers."""
    if not HAS_SENTENCE_TRANSFORMERS:
        raise ImportError("sentence_transformers not available")
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.astype(np.float32)

def generate_pdf_dataset(pdf_dir: str, n_vectors: int, dim: int, n_queries: int, embedder: str = "sentence-transformers", seed: int = 42):
    """Generate dataset from PDF files in directory."""
    random.seed(seed)
    np.random.seed(seed)

    pdf_files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    if not pdf_files:
        raise ValueError("No PDF files found in directory")

    all_texts = []
    for pdf in pdf_files:
        text = extract_text_from_pdf(pdf)
        if text:
            chunks = chunk_text(text)
            all_texts.extend(chunks)

    # Sample texts for vectors
    if len(all_texts) < n_vectors:
        # Duplicate if not enough
        all_texts *= (n_vectors // len(all_texts)) + 1
    selected_texts = random.sample(all_texts, n_vectors)

    # Embed vectors using SentenceTransformers (free and open source)
    if HAS_SENTENCE_TRANSFORMERS:
        vectors = embed_with_sentence_transformers(selected_texts, dim=dim)
    else:
        raise ImportError("sentence_transformers required for embedding")

    # Generate queries (random from texts or synthetic)
    query_texts = random.sample(all_texts, min(n_queries, len(all_texts)))
    if len(query_texts) < n_queries:
        query_texts *= (n_queries // len(query_texts)) + 1
        query_texts = query_texts[:n_queries]

    if HAS_SENTENCE_TRANSFORMERS:
        queries = embed_with_sentence_transformers(query_texts, dim=dim)
    else:
        raise ImportError("sentence_transformers required for embedding")

    return vectors, queries

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
            if enable_payload:
                import random
                metadata = [{
                    "synthetic": True,
                    "id": i,
                    "group": "A" if random.random() < 0.5 else "B"
                } for i in range(n)]
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
