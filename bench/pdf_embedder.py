# bench/pdf_embedder.py
import os, numpy as np, PyPDF2, random
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
import cohere

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

def embed_with_cohere(texts: list, api_key: str, model: str = "embed-english-v3.0", dim: int = 1024) -> np.ndarray:
    """Embed texts using Cohere API."""
    co = cohere.Client(api_key)
    response = co.embed(texts=texts, model=model, input_type="search_document")
    return np.array(response.embeddings, dtype=np.float32)

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

    # Embed vectors
    if embedder == "sentence-transformers":
        if HAS_SENTENCE_TRANSFORMERS:
            vectors = embed_with_sentence_transformers(selected_texts, dim=dim)
        else:
            # Fallback to cohere
            api_key = os.environ.get("COHERE_API_KEY")
            if not api_key:
                raise ValueError("COHERE_API_KEY environment variable required for fallback")
            vectors = embed_with_cohere(selected_texts, api_key, dim=dim)
    elif embedder == "cohere":
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY environment variable required")
        vectors = embed_with_cohere(selected_texts, api_key, dim=dim)
    else:
        raise ValueError("Unsupported embedder")

    # Generate queries (random from texts or synthetic)
    query_texts = random.sample(all_texts, min(n_queries, len(all_texts)))
    if len(query_texts) < n_queries:
        query_texts *= (n_queries // len(query_texts)) + 1
        query_texts = query_texts[:n_queries]

    if embedder == "sentence-transformers":
        if HAS_SENTENCE_TRANSFORMERS:
            queries = embed_with_sentence_transformers(query_texts, dim=dim)
        else:
            # Fallback to cohere
            api_key = os.environ.get("COHERE_API_KEY")
            if not api_key:
                raise ValueError("COHERE_API_KEY environment variable required for fallback")
            queries = embed_with_cohere(query_texts, api_key, dim=dim)
    else:
        queries = embed_with_cohere(query_texts, api_key, dim=dim)

    return vectors, queries