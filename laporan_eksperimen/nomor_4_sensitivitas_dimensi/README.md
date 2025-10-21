# Nomor 4: Sensitivitas terhadap Dimensi Embedding dan Dataset Size

## Dimension and Dataset Size Sensitivity

### Deskripsi Eksperimen

Analisis bagaimana performa database vektor berubah dengan dimensi embedding (384D, 768D, 1536D) dan ukuran dataset pada sensitivity studies dengan parameter ef tuning.

### Dataset yang Diuji

- `msmarco-mini-10k-d384` - Low-dimension baseline
- `openai-ada-10k-d1536` - High-dimension stress test

### File Hasil

- `qdrant_msmarco-mini-10k-d384_sensitivity.json` - Qdrant low-dim sensitivity
- `weaviate_msmarco-mini-10k-d384_sensitivity.json` - Weaviate low-dim sensitivity
- `qdrant_openai-ada-10k-d1536_sensitivity.json` - Qdrant high-dim sensitivity
- `weaviate_openai-ada-10k-d1536_sensitivity.json` - Weaviate high-dim sensitivity

### Folder Analysis

- `qdrant_msmarco-mini-10k-d384_sensitivity/` - Plot sensitivity Qdrant (384D)
- `weaviate_msmarco-mini-10k-d384_sensitivity/` - Plot sensitivity Weaviate (384D)
- `qdrant_openai-ada-10k-d1536_sensitivity/` - Plot sensitivity Qdrant (1536D)
- `weaviate_openai-ada-10k-d1536_sensitivity/` - Plot sensitivity Weaviate (1536D)

### Key Findings

- **Qdrant lebih konsisten**: Performance stabil across semua dimensi
- **Weaviate lebih tunable**: 35-44% recall improvement dengan ef tuning
- **Dimensi impact**: 384D optimal untuk speed, 1536D untuk accuracy
- **Memory critical**: High-dim datasets butuh --limit_n 2000

### Performance by Dimension

- **384D**: Qdrant 1.5x faster (600 vs 400 QPS)
- **1536D**: Qdrant 3x faster (600 vs 200 QPS)

### Recommendations

- **Speed-critical**: Qdrant + 384D dataset
- **Accuracy-critical**: Weaviate with ef=256 + 1536D dataset
- **Balanced**: Qdrant + 768D dataset
