# Nomor 3: Skalabilitas Konkurensi

## Scalability Testing Across Dimensions

### Deskripsi Eksperimen

Uji skalabilitas dengan berbagai dimensi embedding dan ukuran dataset untuk mengidentifikasi bottleneck dan performance patterns pada concurrency 1-2 workers.

### Dataset yang Diuji

- `msmarco-mini-10k-d384` - Baseline (low-dim, 10k vectors)
- `cohere-mini-50k-d768` - Main test (medium-dim, 50k vectors)
- `openai-ada-10k-d1536` - Stress test (high-dim, 10k vectors)

### File Hasil

- `qdrant_msmarco-mini-10k-d384.json` - Qdrant baseline
- `qdrant_cohere-mini-50k-d768.json` - Qdrant main test
- `qdrant_openai-ada-10k-d1536.json` - Qdrant stress test
- `weaviate_msmarco-mini-10k-d384.json` - Weaviate baseline
- `weaviate_cohere-mini-50k-d768.json` - Weaviate main test
- `weaviate_openai-ada-10k-d1536.json` - Weaviate stress test

### Key Findings

- **Qdrant 2x lebih cepat** secara konsisten (500-600 vs 200-400 QPS)
- **Semua test CPU-bound** - NVMe storage tidak menjadi bottleneck
- **Qdrant lebih stabil** across semua dimensi
- **Weaviate perlu memory limit lebih konservatif**

### Memory Limits Used (8GB RAM Laptop)

- 384D datasets: --limit_n 5000
- 768D datasets: --limit_n 5000 (Qdrant), --limit_n 3000 (Weaviate)
- 1536D datasets: --limit_n 2000
