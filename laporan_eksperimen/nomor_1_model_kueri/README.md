# Nomor 1: Model Kueri dan Fitur Sistem

## Payload Filtering vs Hybrid Search

### Deskripsi Eksperimen

Perbandingan antara Qdrant (pure vector search dengan payload filtering) vs Weaviate (hybrid search dengan vector + text search) untuk menentukan trade-off antara throughput dan fitur pada dataset utama `cohere-mini-50k-d768`.

### File Hasil

- `qdrant_cohere-mini-50k-d768.json` - Hasil benchmark Qdrant
- `qdrant_cohere-mini-50k-d768_quick.json` - Hasil benchmark cepat Qdrant
- `weaviate_cohere-mini-50k-d768.json` - Hasil benchmark Weaviate
- `weaviate_cohere-mini-50k-d768_quick.json` - Hasil benchmark cepat Weaviate

### Folder Analysis

- `qdrant_cohere-mini-50k-d768/` - Plot dan analisis Qdrant
- `qdrant_cohere-mini-50k-d768_quick/` - Plot dan analisis Qdrant (mode cepat)
- `weaviate_cohere-mini-50k-d768/` - Plot dan analisis Weaviate
- `weaviate_cohere-mini-50k-d768_quick/` - Plot dan analisis Weaviate (mode cepat)

### Key Findings

- **Qdrant**: 4x lebih cepat (500 QPS vs 125 QPS), pure vector search optimal
- **Weaviate**: Lebih hemat CPU (70-85% vs 200-700%), hybrid search capabilities
- **Trade-off**: Speed vs Resource Efficiency vs Features
