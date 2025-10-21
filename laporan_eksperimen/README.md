# 📊 Laporan Eksperimen Vector Database Benchmark

## Qdrant vs Weaviate - 4 Pertanyaan Penelitian Utama

Folder ini berisi hasil lengkap dari 4 eksperimen benchmark untuk memudahkan pembuatan laporan skripsi/penelitian.

## 📁 Struktur Folder

```
laporan_eksperimen/
├── nomor_1_model_kueri/          # Payload Filtering vs Hybrid Search
├── nomor_2_parameter_hnsw/       # ef Parameter Sensitivity Study
├── nomor_3_skala_konkurensi/     # Scalability Testing
└── nomor_4_sensitivitas_dimensi/ # Dimension & Dataset Size Sensitivity
```

## 📋 Ringkasan 4 Eksperimen

### 1. Model Kueri dan Fitur Sistem

**Fokus**: Perbandingan Qdrant (pure vector) vs Weaviate (hybrid search)
**Dataset**: cohere-mini-50k-d768
**Key Finding**: Qdrant 4x lebih cepat, Weaviate lebih hemat resource

### 2. Penyetelan Parameter HNSW

**Fokus**: Sensitivity study parameter ef (64, 128, 192, 256)
**Dataset**: cohere-mini-50k-d768
**Key Finding**: Qdrant default optimal, Weaviate perlu tuning (+37% recall)

### 3. Skalabilitas Konkurensi

**Fokus**: Performance across dimensions (384D, 768D, 1536D)
**Dataset**: msmarco-mini-10k-d384, cohere-mini-50k-d768, openai-ada-10k-d1536
**Key Finding**: Qdrant 2x lebih cepat, semua CPU-bound

### 4. Sensitivitas Dimensi dan Ukuran Dataset

**Fokus**: Extended sensitivity studies pada additional datasets
**Dataset**: msmarco-mini-10k-d384, openai-ada-10k-d1536
**Key Finding**: Qdrant konsisten, Weaviate tunable (35-44% improvement)

## 📊 File yang Tersedia di Setiap Folder

### JSON Results

- `*_sensitivity.json` - Hasil sensitivity study (ef parameter testing)
- `*.json` - Hasil benchmark standar

### Analysis Folders

- `*_sensitivity/` - Plot dan summary untuk sensitivity studies
- `*/` - Plot dan summary untuk benchmark standar

### README.md

- Deskripsi eksperimen
- File yang ada di folder
- Key findings dan insights

## 🚀 Cara Menggunakan untuk Laporan

1. **Copy folder** yang diperlukan ke dokumen laporan Anda
2. **Gunakan README.md** di setiap folder sebagai referensi
3. **Import JSON files** untuk analisis data lebih detail
4. **Gunakan plot PNG** dari folder analysis untuk visualisasi

## 📈 Overall Performance Summary

| Database     | QPS Range | CPU Usage | Recall@10   | Best For           |
| ------------ | --------- | --------- | ----------- | ------------------ |
| **Qdrant**   | 500-600   | 130-183%  | 0.845-0.939 | High-throughput    |
| **Weaviate** | 200-400   | 78-112%   | 0.772-0.931 | Resource-efficient |

## 💡 Recommendations

- **High-throughput applications**: Qdrant
- **Resource-constrained environments**: Weaviate
- **High-accuracy requirements**: Weaviate with parameter tuning
- **Simple deployment**: Qdrant (less tuning needed)

---

**Environment**: MacBook Pro 13-inch (Intel i5, 8GB RAM, NVMe SSD)
**Date**: October 22, 2025
**Total Experiments**: 4 research questions completed
