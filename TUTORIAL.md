# Tutorial Lengkap: Benchmarking Vector Databases untuk Semantic Search Dokumen PDF

Tutorial ini memandu Anda untuk menjalankan codebase `fp-sdi` dari awal, sesuai dengan metodologi BAB 1-3 penelitian. Codebase ini melakukan benchmarking performa Milvus, Qdrant, dan Weaviate pada skenario semantic search berbasis embedding vektor, dengan fokus pada pipeline PDF → embedding → VDB, payload/metadata/filter, dan hybrid search.

## Prerequisites

Sebelum memulai, pastikan sistem Anda memenuhi syarat berikut:

- **OS**: macOS, Linux, atau Windows dengan WSL2.
- **Docker & Docker Compose**: Versi terbaru (Docker >= 20.10, Compose >= 2.0).
  - Install dari [docker.com](https://www.docker.com/).
- **NVMe SSD**: Untuk performa optimal, gunakan NVMe terdedikasi (mount ke `/Volumes/NVMe/vdb` di macOS atau path serupa).
- **Python**: Tidak diperlukan di host, karena semua berjalan di container.
- **Ruang Disk**: Minimal 10GB untuk dataset dan container.
- **Akses Internet**: Untuk download model embedding dan Docker images.

### Verifikasi Prerequisites

```bash
# Cek Docker
docker --version
docker compose version

# Cek NVMe (opsional, untuk performa)
df -h | grep -i nvme
```

## Setup Codebase

1. **Clone atau Download Repository**:

   ```bash
   git clone https://github.com/dzaky-pr/fp-sdi.git
   cd fp-sdi
   ```

2. **Set Environment Variable untuk NVMe** (Opsional, default ke `./nvme`):

   ```bash
   export NVME_ROOT=/Volumes/NVMe/vdb  # Ganti dengan path NVMe Anda
   ```

3. **Build Bench Container**:

   ```bash
   docker compose build bench
   ```

   Ini akan build container `bench` dengan semua dependencies (Python, libraries untuk PDF/embedding).

## Menjalankan Benchmark

### 1. Pilih Vector Database

Codebase mendukung Milvus, Qdrant, dan Weaviate. Pilih satu untuk eksperimen.

- **Milvus**: Mendukung IVF, HNSW, DiskANN.
- **Qdrant**: HNSW dengan on_disk.
- **Weaviate**: HNSW dengan hybrid search.

### 2. Jalankan Database dan Bench Container

Gunakan Makefile untuk kemudahan:

```bash
# Untuk Milvus
make up-milvus

# Untuk Qdrant
make up-qdrant

# Untuk Weaviate
make up-weaviate
```

Atau manual:

```bash
# Milvus
docker compose --profile milvus --profile bench up -d milvus bench

# Qdrant
docker compose --profile qdrant --profile bench up -d qdrant bench

# Weaviate
docker compose --profile weaviate --profile bench up -d weaviate bench
```

Tunggu hingga container sehat (healthcheck di docker-compose.yml).

### 3. Masuk ke Bench Container

```bash
make bench-shell
# Atau: docker compose exec bench bash
```

### 4. Install Dependencies (Jika Belum)

Di dalam container:

```bash
pip install -r requirements.txt
```

### 5. Konfigurasi (Opsional)

Edit `bench/config.yaml` untuk:

- `pdf_dir`: Path ke folder PDF (default `/datasets/pdfs`).
- `embedder`: "sentence-transformers" atau "cohere" (set `COHERE_API_KEY` jika cohere).
- `enable_payload_filter`: true untuk eksperimen metadata/filter.
- `enable_hybrid_search`: true untuk hybrid di Weaviate.
- Dataset: `cohere-mini-200k-d768` (768 dim) atau `openai-mini-50k-d1536` (1536 dim).

### 6. Jalankan Benchmark

Di dalam container:

```bash
# Contoh: Benchmark Milvus dengan IVF pada dataset 768 dim
python bench.py --db milvus --index ivf --dataset cohere-mini-200k-d768

# Contoh: Benchmark Qdrant dengan HNSW
python bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768

# Contoh: Benchmark Weaviate dengan HNSW
python bench.py --db weaviate --index hnsw --dataset cohere-mini-200k-d768

# Baseline I/O (fio)
python bench.py --baseline
```

Output akan disimpan sebagai JSON di terminal (copy-paste ke file jika perlu, e.g., `results.json`).

### 7. Analisis Hasil

Setelah benchmark, analisis hasil:

```bash
# Simpan output ke file (contoh)
python bench.py --db milvus --index hnsw --dataset cohere-mini-200k-d768 > results_milvus_hnsw.json

# Analisis dan plot
python analyze_results.py --results results_milvus_hnsw.json --output results/
```

Ini akan generate plot PNG (QPS vs concurrency, P99 vs concurrency, CPU vs concurrency) dan summary JSON.

## Contoh Pemakaian Lengkap

### Skenario: Benchmark Milvus dengan DiskANN pada Dataset dari PDF

1. **Siapkan PDF**:

   - Pastikan `paper_rujukan.pdf` ada di `/datasets/pdfs/`.
   - Set `pdf_dir: "/datasets/pdfs"` di `config.yaml`.

2. **Jalankan Setup**:

   ```bash
   export NVME_ROOT=/Volumes/NVMe/vdb
   make up-milvus
   make bench-shell
   pip install -r requirements.txt
   ```

3. **Jalankan Benchmark**:

   ```bash
   python bench.py --db milvus --index diskann --dataset cohere-mini-200k-d768 > results_diskann.json
   ```

4. **Output Contoh** (JSON):

   ```json
   [
     {"conc": 1, "qps": 150.5, "p50": 5.2, "p95": 12.1, "p99": 25.3, "cpu": 45.2, "read_mb": 120.5, "write_mb": 0.1, "total_mb": 120.6, "avg_bandwidth_mb_s": 85.3, "repeats": 5},
     {"conc": 2, "qps": 280.1, "p50": 6.8, "p95": 15.2, "p99": 35.7, "cpu": 68.9, "read_mb": 240.2, "write_mb": 0.2, "total_mb": 240.4, "avg_bandwidth_mb_s": 170.1, "repeats": 5},
     ...
   ]
   ```

5. **Analisis**:
   ```bash
   python analyze_results.py --results results_diskann.json --output results/
   ```
   - Lihat plot di `results/qps_concurrency.png`, dll.
   - Summary: Max QPS, min P99, avg CPU, bottleneck analysis (CPU-bound jika QPS turun drastis).

### Eksperimen Payload/Filter

- Set `enable_payload_filter: true` di `config.yaml`.
- Benchmark akan include metadata (e.g., doc_type) dan filter di Qdrant/Weaviate.

### Eksperimen Hybrid Search

- Set `enable_hybrid_search: true`.
- Hanya untuk Weaviate, akan combine vector + keyword search.

## Troubleshooting

- **Container Tidak Start**: Cek logs `docker compose logs [service]`.
- **Out of Memory**: Kurangi dataset size atau concurrency.
- **Embedding Gagal**: Pastikan PDF ada atau gunakan synthetic (hapus pdf_dir).
- **I/O Error**: Pastikan NVMe mounted dengan benar.
- **Cohere API**: Set `export COHERE_API_KEY=your_key` di host sebelum run container.

## Cleanup

```bash
make down  # Stop dan remove container
docker system prune  # Bersihkan unused images
```

Tutorial ini memastikan replikasi metodologi BAB 1-3: single-machine, NVMe, 30s/1000 query, flush cache, 5 ulangan, tuning recall@10 ≥0.9, dan analisis kuantitatif. Untuk pertanyaan, lihat BAB 1-3 atau paper rujukan.
