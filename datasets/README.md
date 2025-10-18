# Datasets

This directory contains vector datasets for benchmarking.

## Required Files:
- `cohere-mini-200k-d768/vectors.npy` (585MB) - Vector embeddings for benchmarking
- `cohere-mini-200k-d768/queries.npy` - Query vectors for testing

## Note:
Large dataset files are excluded from git due to size limits.
Download or generate your own datasets following the paper methodology.

## Dataset Format:
- Vectors: numpy array shape (N, 768) dtype=float32
- Queries: numpy array shape (M, 768) dtype=float32

Where N = dataset size (e.g., 200k), M = number of queries (e.g., 1000)
