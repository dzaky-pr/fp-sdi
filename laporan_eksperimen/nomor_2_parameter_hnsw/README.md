# Nomor 2: Penyetelan Parameter HNSW

## ef_search vs ef Parameter Sensitivity

### Deskripsi Eksperimen

Analisis sensitivitas parameter ef (exploration factor) pada algoritma HNSW untuk menemukan optimal balance antara akurasi (recall@10) dan performa (QPS) pada dataset `cohere-mini-50k-d768`.

### Parameter yang Diuji

- ef values: 64, 128, 192, 256
- Concurrency: 1-2 workers
- Dataset: cohere-mini-50k-d768 (50k vectors, 768D)

### File Hasil

- `qdrant_cohere-mini-50k-d768_sensitivity.json` - Hasil sensitivity study Qdrant
- `weaviate_cohere-mini-50k-d768_sensitivity.json` - Hasil sensitivity study Weaviate

### Folder Analysis

- `qdrant_cohere-mini-50k-d768_sensitivity/` - Plot dan analisis sensitivity Qdrant
- `weaviate_cohere-mini-50k-d768_sensitivity/` - Plot dan analisis sensitivity Weaviate

### Key Findings

- **Qdrant**: Default ef=64 sudah optimal, tidak perlu tuning (recall konsisten 0.917)
- **Weaviate**: Significant improvement dengan ef tuning (+37% recall dari 0.644 ke 0.880)
- **Qdrant lebih "forgiving"**: Default parameters excellent
- **Weaviate lebih "tunable"**: Parameter optimization memberikan besar impact
