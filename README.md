# Vector Database Benchmark: Qdrant vs Weaviate

> Perbandingan performa Qdrant vs Weaviate untuk semantic search pada dokumen PDF, mengikuti metodologi paper rujukan dengan fokus pada HNSW-based comparison.

## 📊 Overview

### Mengapa Hanya Qdrant vs Weaviate?

**Milvus dikecualikan** karena:

- Resource-intensive (butuh 8GB+ RAM)
- Unstable di macOS/laptop (sering crash)
- API kompleks dan sering berubah
- **Fokus apple-to-apple**: Qdrant & Weaviate sama-sama pakai HNSW

### Objective Utama Perbandingan

Nah, kenapa sih kita bandingin Qdrant sama Weaviate? Karena kita pengen bantu orang-orang kayak developer, peneliti, atau bahkan bisnis kecil buat pilih database vektor yang pas buat cari dokumen PDF secara cerdas. Bayangin aja, cari info dari PDF pake AI, bukan cuma keyword biasa.

**Tujuan Akhirnya** (terinspirasi dari paper rujukan yang skala besar):

- **Cari tahu kekuatan masing-masing**: Qdrant tuh lebih cepat dan hemat resource di laptop biasa, cocok buat app yang butuh respon kilat. Weaviate lebih kaya fitur, kayak bisa gabung pencarian teks sama vektor, jadi lebih fleksibel buat app kompleks.
- **Bikin riset besar jadi praktis**: Paper-paper sering pakai server gede, tapi kita buktin di laptop aja bisa, biar hemat biaya buat kuliah atau startup kecil.
- **Dorong kreativitas AI**: Hasil benchmark ini bisa jadi inspirasi buat bikin app keren kayak chatbot yang bisa jawab dari PDF, atau AI yang cari info otomatis – tanpa perlu beli hardware mahal.
- **Bantu tugas kuliah atau riset**: Data ini bisa langsung dipake buat skripsi, dengan perbandingan yang adil dan bisa diulang orang lain.

Pokoknya, proyek ini mau bikin pencarian cerdas pake AI lebih gampang diakses sama dipilih, buat siapa aja yang mau inovasi di dunia digital.

---

### Validitas Penelitian

| Aspek          | Qdrant                           | Weaviate                         | Status  |
| -------------- | -------------------------------- | -------------------------------- | ------- |
| **Index**      | HNSW                             | HNSW                             | ✅ Sama |
| **Deployment** | Docker                           | Docker                           | ✅ Sama |
| **Storage**    | NVMe                             | NVMe                             | ✅ Sama |
| **Execution**  | Sequential (satu database aktif) | Sequential (satu database aktif) | ✅ Sama |

**Sesuai Paper Rujukan**:

- ✅ Single-machine Docker setup
- ✅ NVMe storage dengan dedicated volumes
- ✅ Standardized metrics (QPS, P99 latency, recall@10)
- ✅ Fair parameter tuning hingga recall ≥ 0.9
- ✅ Multiple runs (5× repeats) untuk reliability
- ✅ **Sequential execution** untuk fairness comparison

**Sesuai Batasan Studi (Bab 1-3)**:

- ✅ Docker-based only (LanceDB dikecualikan)
- ✅ Laptop/workstation environment
- ✅ HNSW focus (Milvus IVF/DiskANN tidak diperlukan)

---

## 🔍 How Search/Query Works (Big Picture)

Proyek ini **bukan aplikasi pencarian end-user**, tapi **benchmark otomatis** untuk ukur performa. Search di sini adalah **semantic search berbasis vektor** (bukan teks keyword), menggunakan embeddings untuk temukan kemiripan.

### Contoh Sederhana:

- **Query**: Bukan teks seperti "cari mobil", tapi **vektor numerik** (array float, dimensi 768). Contoh: `[0.123, -0.456, 0.789, ..., 0.001]` (dari embed teks atau random).
- **Proses**: Kirim vektor query ke database (Qdrant/Weaviate), dapatkan top-10 vektor paling mirip (berdasarkan cosine similarity). Hasil: ID dokumen, bukan teks.
- **Tujuan**: Ukur QPS (query per detik), latency, recall – bukan tampilkan hasil ke user.
- **Dataset**: Dari PDF (embed teks jadi vektor) atau synthetic (random vektor).

Ini membantu bayang big picture: Benchmark membandingkan cepat/lambat database dalam handle query vektor, untuk riset semantic search pada PDF.

### Apa Itu HNSW? Kenapa Tuning Comparable?

- **HNSW (Hierarchical Navigable Small World)**: Algoritma untuk cari "tetangga terdekat" dalam data vektor high-dimensional (seperti embeddings 768D). Lebih cepat dari brute force, tapi approximate (kurang akurat untuk trade-off speed).
- **Tuning Comparable**: Qdrant & Weaviate sama-sama pakai HNSW, jadi parameter seperti `ef` (exploration factor – seberapa dalam cari untuk akurasi) bisa dibandingkan langsung. Contoh: ef=128 di keduanya berarti eksplorasi sama, hasil fair.

---

## File Structure

Proyek ini telah dioptimalkan menjadi 6 file Python utama untuk kemudahan maintenance, tanpa merusak logic atau flow benchmark. Berikut penjelasan fungsi masing-masing file:

### `bench.py`

- **Fungsi Utama**: Script entry point untuk menjalankan benchmark.
- **Detail**: Mengatur concurrency grid, tuning parameter HNSW (ef search), dan orchestrasi seluruh proses benchmark. Mendukung mode sensitivity study dan baseline I/O test. Menggunakan ThreadPoolExecutor untuk simulasi concurrency.

### `clients.py`

- **Fungsi Utama**: Wrapper class untuk client database vector (Qdrant dan Weaviate).
- **Detail**: Berisi class `QdrantClientHelper` dan `WeaviateClient` dengan method standar: `connect()`, `drop_recreate()`, `insert()`, `search()`. Memungkinkan ekstensi mudah untuk database baru tanpa mengubah logic utama.

### `datasets.py`

- **Fungsi Utama**: Pembuatan dan pemuatan dataset untuk benchmark.
- **Detail**: Menghasilkan embedding dari PDF menggunakan SentenceTransformers (gratis dan open source), atau data synthetic. Mendukung hybrid search dengan sparse vectors (BM25). Cache dataset ke file .npy untuk efisiensi. Dataset tersedia: `msmarco-mini-10k-d384`, `cohere-mini-50k-d768`, `openai-ada-10k-d1536`.

### `monitoring.py`

- **Fungsi Utama**: Monitoring performa sistem selama benchmark.
- **Detail**: Monitor CPU usage dari Docker container, I/O traces (bpftrace/iostat fallback), dan page cache flush. Termasuk FIO baseline test untuk disk performance.

### `utils.py`

- **Fungsi Utama**: Utility functions umum.
- **Detail**: Hitung percentile (P50, P95, P99), brute-force top-k search untuk ground truth, recall calculation, dan flush page cache. Digunakan di seluruh proyek untuk metrik dan helper.

### `analyze_results.py`

- **Fungsi Utama**: Analisis dan visualisasi hasil benchmark.
- **Detail**: Membaca JSON hasil, membuat plot QPS vs concurrency, P99 latency, CPU usage. Menghasilkan summary stats dan bottleneck analysis (CPU-bound vs I/O-bound).

---

## 🚀 Quick Start

### Prerequisites

```bash
# Check Docker (REQUIRED)
docker --version  # Minimal v24.0+
docker compose version  # Minimal v2.23+

# Check Python (REQUIRED for analysis)
python3 --version  # Minimal v3.8, recommended v3.12

# Check disk space (REQUIRED)
df -h .  # Minimal 10GB free
```

### Setup

```bash
# 1. Clone repository
git clone https://github.com/dzaky-pr/fp-sdi.git
cd fp-sdi

# 2. Setup Python virtual environment
python3.12 -m venv venv  # Use python3.12 if available, otherwise python3
source venv/bin/activate
pip install -r bench/requirements.txt

# 3. Setup NVMe storage path (KRITIS - HARUS sesuai!)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
mkdir -p "$NVME_ROOT"

# Verify path (HARUS output: /Users/dzakyrifai/nvme-vdb)
echo "$NVME_ROOT"

# 4. Build containers
make build

# 5. Start services (gunakan export NVME_ROOT jika belum permanent)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up

# 6. Verify setup
make test-all
```

### Run Benchmarks

**⚠️ IMPORTANT**: Jalankan benchmark **SATU PER SATU** untuk fairness comparison. Jangan jalankan kedua database bersamaan karena akan berebut resource.

```bash
# Enter benchmark container
make bench-shell

# ===========================================
# RUN QDRANT BENCHMARK (Stop Weaviate first)
# ===========================================
# From host terminal (bukan di bench-shell):
docker compose stop weaviate

# Then in bench-shell:
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768

# ===========================================
# RUN WEAVIATE BENCHMARK (Stop Qdrant first)
# ===========================================
# From host terminal (bukan di bench-shell):
docker compose stop qdrant && docker compose start weaviate

# Then in bench-shell:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768

# Mode Cepat (≤5 menit per run) - REKOMENDASI UNTUK PEMULA:
# Mode cepat (≤5 menit per run) - REKOMENDASI UNTUK PEMULA:
python3 bench.py --db qdrant   --index hnsw --dataset cohere-mini-50k-d768 --quick5
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --quick5


# Optional: Run on all datasets for comprehensive comparison
# ===========================================
# BASELINE (Low-dim) - Qdrant
# ===========================================
# From host: docker compose stop weaviate
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384 > /app/results_qdrant_baseline.json

# ===========================================
# BASELINE (Low-dim) - Weaviate
# ===========================================
# From host: docker compose stop qdrant && docker compose start weaviate
python3 bench.py --db weaviate --index hnsw --dataset msmarco-mini-10k-d384 > /app/results_weaviate_baseline.json

# ===========================================
# STRESS (High-dim) - Qdrant
# ===========================================
# From host: docker compose stop weaviate
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536 > /app/results_qdrant_stress.json

# ===========================================
# STRESS (High-dim) - Weaviate
# ===========================================
# From host: docker compose stop qdrant && docker compose start weaviate
python3 bench.py --db weaviate --index hnsw --dataset openai-ada-10k-d1536 > /app/results_weaviate_stress.json

# Exit bench container
exit

# Analyze results (compare all datasets)
python3 bench/analyze_results.py --results results_qdrant_baseline.json results_weaviate_baseline.json results_qdrant.json results_weaviate.json results_qdrant_stress.json results_weaviate_stress.json
```

---

## 📋 Detailed Setup Guide

### 1. System Requirements

**Minimum**:

- Docker Desktop 24.0+
- 8GB RAM
- 10GB free disk space
- macOS/Linux/Windows

**Recommended**:

- 16GB RAM
- NVMe SSD
- macOS (Intel/Apple Silicon) or Linux

### 2. Python Environment Setup

```bash
# Setup virtual environment
python3.12 -m venv venv  # Use python3.12 if available
source venv/bin/activate

# Install dependencies
pip install -r bench/requirements.txt

# Verify installation
python3 -c "import pandas, matplotlib, numpy, pyyaml; print('All dependencies installed')"
```

### 3. NVMe Storage Setup

⚠️ **KRITIS**: Path HARUS `/Users/dzakyrifai/nvme-vdb` (sesuai hardware MacBook Pro Intel)

```bash
# Setup NVMe internal path (PAKAI INI - JANGAN DIGANTI!)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
mkdir -p "$NVME_ROOT"

# VERIFICATION KRITIS (jalankan semua!)
echo "$NVME_ROOT"                    # HARUS: /Users/dzakyrifai/nvme-vdb
ls -la "$NVME_ROOT"                  # Check directory exists
df -h "$NVME_ROOT"                   # Check NVMe mount point
du -sh "$NVME_ROOT"                  # Check current usage

# Make permanent (recommended)
echo 'export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"' >> ~/.zshrc
source ~/.zshrc
```

**Konfirmasi Volume Mapping:**

- **Qdrant**: `${NVME_ROOT}/qdrant:/qdrant/storage`
- **Weaviate**: `${NVME_ROOT}/weaviate:/var/lib/weaviate`
- **FIO**: `${NVME_ROOT}/fio:/target`

❌ **JANGAN gunakan**:

- `/System/*` - System files
- `/usr/*` - System binaries
- `/` - Root filesystem
- `~/nvme-vdb` - Tidak akan resolve dengan benar di Docker

### 4. Build & Start Services

```bash
# Build benchmark container
make build

# Start Qdrant + Weaviate (PAKAI export NVME_ROOT!)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up

# Check services
docker compose ps
# Expected: qdrant (healthy), weaviate (healthy), bench (up)

# Test connectivity
make test-all
```

### 5. Run Benchmarks

**⚠️ KRITIS**: Benchmark dijalankan **SATU PER SATU** untuk fairness. Jangan jalankan paralel karena berebut resource!

**Workflow Sequential**:

1. Start semua services dengan `make up`
2. Masuk bench container dengan `make bench-shell`
3. Stop database yang tidak digunakan
4. Jalankan benchmark untuk database yang aktif
5. Switch database dan ulangi

```bash
# Enter container
make bench-shell

# ===========================================
# QDRANT BENCHMARKS
# ===========================================
# Stop Weaviate (dari terminal host, bukan bench-shell):
docker compose stop weaviate

# Jalankan benchmarks Qdrant (di bench-shell):
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536

# ===========================================
# WEAVIATE BENCHMARKS
# ===========================================
# Stop Qdrant & start Weaviate (dari terminal host):
docker compose stop qdrant && docker compose start weaviate

# Jalankan benchmarks Weaviate (di bench-shell):
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768
python3 bench.py --db weaviate --index hnsw --dataset msmarco-mini-10k-d384
python3 bench.py --db weaviate --index hnsw --dataset openai-ada-10k-d1536

# Optional: Sensitivity study (recall vs QPS trade-off)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --sensitivity

# Exit
exit
```

**Mengapa Sequential?**

- **Fairness**: Setiap database dapat full resource (CPU, RAM, I/O)
- **Accuracy**: Tidak ada interference antar database
- **Reliability**: Benchmark lebih stabil dan reproducible
- **Resource Efficiency**: Laptop/workstation terbatas resource

### 6. Analyze Results

```bash
# Compare results
python3 bench/analyze_results.py --results results_qdrant.json results_weaviate.json

# Generate plots (optional)
python3 bench/analyze_results.py --results results_qdrant.json results_weaviate.json
```

---

## 📊 Expected Performance

Berdasarkan testing di MacBook Pro 13-inch (2020, Intel Core i5, 8GB RAM) dengan dataset `cohere-mini-50k-d768` (50k vectors, 768D). **Benchmark dijalankan sequential** (satu database aktif) untuk fairness.

### Qdrant

```
Concurrency=1: ~125-500 QPS, CPU: 200-700%, I/O: 0.17-0.21 MB/s
Recall@10: ~0.11 (ef=64)
```

### Weaviate

```
Concurrency=1: ~125 QPS, CPU: 70-85%, I/O: 0.13 MB/s
Recall@10: ~0.14 (ef=64)
```

### Trade-offs

| Aspect        | Qdrant                   | Weaviate               |
| ------------- | ------------------------ | ---------------------- |
| **QPS**       | ⚡ Higher (125-500)      | Lower (125)            |
| **CPU Usage** | Higher (200-700%)        | Lower (70-85%)         |
| **I/O**       | Similar (0.13-0.21 MB/s) | Similar (0.13 MB/s)    |
| **Features**  | Payload filtering        | Hybrid search, GraphQL |
| **Ecosystem** | Python-first             | Multi-language         |

---

## � HNSW Parameter Sensitivity Study

### Overview

Sensitivity study menguji trade-off antara **akurasi (recall@10)** vs **performa (QPS)** dengan variasi parameter `ef` (exploration factor) pada algoritma HNSW. Nilai ef tinggi meningkatkan akurasi pencarian tapi menurunkan throughput karena lebih banyak komputasi eksplorasi kandidat tetangga.

### Methodology

- **Parameter Range**: ef = 64, 128, 192, 256
- **Dataset**: `cohere-mini-50k-d768` (50k vectors, 768D)
- **Concurrency**: 1-2 workers
- **Repeats**: 5× untuk reliability
- **Duration**: 10 detik per test
- **Budget**: 600 detik total per database

### Results Summary

#### Qdrant (ef_search parameter)

| ef_search | Recall@10 | Max QPS | CPU Usage | I/O (MB/s) |
| --------- | --------- | ------- | --------- | ---------- |
| 64        | 0.139     | 600     | 183%      | 0.17       |
| 128       | 0.211     | 400     | 183%      | 0.17       |
| 192       | 0.295     | 200     | 183%      | 0.17       |
| 256       | 0.356     | 200     | 183%      | 0.17       |

#### Weaviate (ef parameter)

| ef  | Recall@10 | Max QPS | CPU Usage | I/O (MB/s) |
| --- | --------- | ------- | --------- | ---------- |
| 64  | 0.075     | 300     | 112%      | 0.11       |
| 128 | 0.148     | 300     | 112%      | 0.11       |
| 192 | 0.225     | 200     | 112%      | 0.11       |
| 256 | 0.286     | 200     | 112%      | 0.11       |

### Key Findings

#### 1. Recall vs QPS Trade-off

- **Qdrant**: Recall meningkat signifikan (0.139→0.356) dengan ef, tapi QPS drop drastis setelah ef=128
- **Weaviate**: Recall pattern serupa (0.075→0.286) tapi QPS lebih konsisten, kurang sensitif terhadap ef
- **Optimal ef**: 128-192 untuk balance recall ≥0.2 tanpa QPS penalty berat

#### 2. Resource Utilization

- **CPU-bound**: Kedua database CPU-bound (Qdrant: 183%, Weaviate: 112%)
- **I/O Stability**: I/O bandwidth stabil across ef values, menunjukkan bukan bottleneck
- **Qdrant lebih agresif**: Higher CPU usage tapi lebih efektif untuk ef tuning

#### 3. Performance Comparison

- **Qdrant**: 2× faster than Weaviate pada ef tinggi (600 vs 300 QPS)
- **Weaviate**: Lebih efisien CPU tapi recall growth lebih gradual
- **Convergence**: Kedua database mencapai recall ~0.28-0.35 pada ef=256

### Recommendations

#### For Speed-Critical Applications

```bash
# Qdrant dengan ef_search=128 (optimal balance)
ef_search: 128  # Recall ~0.21, QPS ~400
```

#### For Accuracy-Critical Applications

```bash
# Qdrant dengan ef_search=256 (maximum recall)
ef_search: 256  # Recall ~0.36, QPS ~200
```

#### For Resource-Constrained Environments

```bash
# Weaviate dengan ef=128 (lower CPU usage)
ef: 128  # Recall ~0.15, QPS ~300, CPU ~112%
```

### Visualization

Hasil sensitivity study dapat divisualisasikan dengan:

```bash
# Generate plots untuk sensitivity analysis
python3 bench/analyze_results.py --results results/qdrant_cohere-mini-50k-d768_sensitivity.json results/weaviate_cohere-mini-50k-d768_sensitivity.json --output results/sensitivity_analysis
```

Plot yang dihasilkan:

- `qps_vs_ef.png`: QPS vs ef parameter
- `recall_vs_ef.png`: Recall@10 vs ef parameter
- `cpu_vs_ef.png`: CPU usage vs ef parameter
- `bottleneck_analysis.png`: Resource utilization breakdown

---

## �🛠️ Configuration

### Dataset

Dataset dipilih berdasarkan kategori untuk coverage komprehensif: baseline (low-dim), main (medium-dim), dan stress (high-dim). Ini memungkinkan pengujian performa dari skala kecil hingga besar, sesuai metodologi paper rujukan.

| Kategori                  | Dataset                 | Tujuan                                       | Dimensi | Vektor | Query |
| ------------------------- | ----------------------- | -------------------------------------------- | ------- | ------ | ----- |
| 🧪 **Baseline (Low-dim)** | `msmarco-mini-10k-d384` | Pengujian kecepatan dasar, efisiensi RAM     | 384     | 10k    | 1k    |
| ⚙️ **Main (Medium-dim)**  | `cohere-mini-50k-d768`  | Pengujian utama, representatif paper rujukan | 768     | 50k    | 1k    |
| 🧮 **Stress (High-dim)**  | `openai-ada-10k-d1536`  | Sensitivitas terhadap dimensi embedding      | 1536    | 10k    | 1k    |

**Alasan Pemilihan**:

- **msmarco-mini-10k-d384**: Low-dim untuk baseline cepat, hemat RAM di laptop.
- **cohere-mini-50k-d768**: Medium-dim sebagai main test, mirip dataset paper rujukan.
- **openai-ada-10k-d1536**: High-dim untuk stress test dimensi, menguji skalabilitas.

Edit `bench/config.yaml`:

```yaml
datasets:
  - name: msmarco-mini-10k-d384
    n_vectors: 10000
    n_queries: 1000
    dim: 384
  - name: cohere-mini-50k-d768
    n_vectors: 50000
    n_queries: 1000
    dim: 768
  - name: openai-ada-10k-d1536
    n_vectors: 10000
    n_queries: 1000
    dim: 1536
```

### HNSW Parameters

```yaml
indexes:
  qdrant:
    hnsw:
      build:
        ef_construct: 200
        m: 16
      search:
        ef_search_start: 64
        ef_search_max: 256

  weaviate:
    hnsw:
      build:
        efConstruction: 200
        maxConnections: 16
      search:
        ef_start: 64
        ef_max: 256
```

### Benchmark Settings

```yaml
concurrency_grid: [1, 2] # Test different concurrency levels
run_seconds: 10 # Duration per run
repeats: 5 # Number of repeats
target_recall_at_k: 0.9 # Minimum recall
```

---

## 🧪 Commands Reference

### Make Commands

```bash
make help        # Show all commands
make build       # Build containers
make up          # Start services
make down        # Stop services
make clean       # Remove volumes
make bench-shell # Enter benchmark container
make test-all    # Test connectivity
```

### Database Switching Commands

```bash
# Switch to Qdrant only (stop Weaviate)
docker compose stop weaviate

# Switch to Weaviate only (stop Qdrant)
docker compose stop qdrant && docker compose start weaviate

# Start all services
docker compose start qdrant weaviate bench
```

### Benchmark Options

```bash
# Quick benchmark (mode cepat ≤5 menit per database)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --quick5

# Standard benchmark (mode lengkap untuk penelitian)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768

# Benchmark on different datasets
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384    # Baseline (low-dim)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768     # Main (medium-dim)
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536     # Stress (high-dim)

# Sensitivity study (parameter tuning ef_search/ef)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --sensitivity

# I/O baseline test
python3 bench.py --baseline

# Custom embeddings
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --embeddings_npy path/to/custom.npy
```

---

## 🔧 Troubleshooting

### Services Won't Start

```bash
# Check Docker
docker ps

# Restart services
make down && make up

# Check logs
docker compose logs qdrant
docker compose logs weaviate
```

### Healthcheck Issues

**Problem**: Container stuck di "waiting" atau "health: starting" meskipun service sudah running.

**Symptoms**:

- `docker compose ps` menunjukkan `health: starting` atau `unhealthy`
- Service endpoint accessible via curl tapi healthcheck gagal
- Logs menunjukkan service sudah listening di port yang benar

**Root Cause**:

- Container Qdrant tidak punya `curl`/`wget` terinstall
- Container Weaviate punya `wget` tapi healthcheck menggunakan `curl`

**Solutions**:

```bash
# Check if tools available in containers
docker compose exec qdrant which curl  # Should fail
docker compose exec weaviate which wget  # Should succeed

# If healthcheck fails, restart services
make down && make up

# Manual healthcheck test
curl -s http://localhost:6333/healthz  # Qdrant
curl -s http://localhost:8080/v1/meta  # Weaviate

# Force recreate containers if needed
docker compose up --force-recreate -d
```

### Low Performance

```bash
# Check resources
docker stats

# Reduce dataset size (config.yaml)
n_vectors: 10000  # Instead of 25000

# Disable disk storage for Qdrant (higher memory usage)
on_disk: false
```

### Memory Issues (Error 137)

**Problem**: Benchmark exits with code 137 (out of memory) on larger datasets.

**Symptoms**:

- Command exits immediately with code 137
- No error messages shown
- Happens on datasets with >10k vectors

**Solutions**:

```bash
# Use --limit_n to reduce dataset size:
# For medium datasets (768D):
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000

# For high-dim datasets (1536D):
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536 --limit_n 2000

# Restart bench container to free memory:
docker compose restart bench

# Check memory usage:
docker stats
```

---

## 📊 Benchmark Results Summary

Berikut adalah hasil lengkap analisis untuk **4 Pertanyaan Penelitian Utama** berdasarkan benchmark komprehensif Qdrant vs Weaviate pada laptop 8GB RAM.

---

### **NOMOR 1: Model Kueri dan Fitur Sistem (Payload Filtering vs Hybrid Search)**

**Konsep**: Perbandingan antara pure vector search (Qdrant) vs hybrid search (Weaviate) untuk menentukan trade-off antara throughput dan fitur.

#### **Qdrant (Payload Filtering - Pure Vector Search)**

- **QPS**: **500.0** (4x lebih cepat!)
- **CPU Usage**: 407% (full CPU utilization)
- **Recall@10**: 0.917 (tinggi)
- **Bottleneck**: CPU-bound
- **Fitur Utama**: Pure vector similarity search dengan payload filtering

#### **Weaviate (Hybrid Search - Vector + Text)**

- **QPS**: **125.0** (25% dari Qdrant)
- **CPU Usage**: 81% (5x lebih efisien)
- **Recall@10**: 0.772 (lebih rendah)
- **Bottleneck**: CPU-bound
- **Fitur Utama**: Hybrid search (vector + BM25 text search)

#### **Key Findings Nomor 1**:

- **Qdrant 4x lebih cepat** untuk pure vector search
- **Trade-off klasik**: Speed vs Resource Efficiency vs Features
- **Qdrant** cocok untuk high-throughput vector-only applications
- **Weaviate** cocok untuk resource-constrained hybrid search applications

---

### **NOMOR 2: Penyetelan Parameter HNSW (ef_search vs ef)**

**Konsep**: Analisis sensitivitas parameter ef (exploration factor) untuk menemukan optimal balance antara akurasi dan performa.

#### **Qdrant ef Parameter Study**

| ef Value | Recall@10 | QPS Range | CPU Usage | Status            |
| -------- | --------- | --------- | --------- | ----------------- |
| **64**   | **0.917** | 400-500   | 143-154%  | ✅ **Optimal**    |
| **128**  | **0.917** | 400-500   | 143-154%  | ⚪ No improvement |
| **192**  | **0.917** | 400-500   | 143-154%  | ⚪ No improvement |
| **256**  | **0.917** | 400-500   | 143-154%  | ⚪ No improvement |

#### **Weaviate ef Parameter Study**

| ef Value | Recall@10 | QPS Range | CPU Usage | Improvement     |
| -------- | --------- | --------- | --------- | --------------- |
| **64**   | 0.644     | 100-200   | 76-81%    | Baseline        |
| **128**  | **0.816** | 100-200   | 76-81%    | **+27% recall** |
| **192**  | **0.864** | 100-200   | 76-81%    | **+34% recall** |
| **256**  | **0.880** | 100-200   | 76-81%    | **+37% recall** |

#### **Key Findings Nomor 2**:

- **Qdrant**: Default ef=64 sudah optimal, tidak perlu tuning
- **Weaviate**: Significant improvement dengan ef tuning (+37% recall)
- **Qdrant lebih "forgiving"** - default parameters sudah excellent
- **Weaviate lebih "tunable"** - parameter optimization memberikan besar impact

---

### **NOMOR 3: Skalabilitas Konkurensi (Scalability Testing)**

**Konsep**: Uji skalabilitas dengan berbagai dimensi embedding dan ukuran dataset untuk mengidentifikasi bottleneck dan performance patterns.

#### **Qdrant Scalability Results**

| Dataset                 | Dimensi | Max QPS | Recall@10 | Memory Limit | Status     |
| ----------------------- | ------- | ------- | --------- | ------------ | ---------- |
| `cohere-mini-50k-d768`  | 768D    | **500** | 0.917     | 5000 vectors | ✅ Success |
| `msmarco-mini-10k-d384` | 384D    | **600** | 0.845     | 5000 vectors | ✅ Success |
| `openai-ada-10k-d1536`  | 1536D   | **600** | 0.956     | 1000 vectors | ✅ Success |

#### **Weaviate Scalability Results**

| Dataset                 | Dimensi | Max QPS | Recall@10 | Memory Limit | Status     |
| ----------------------- | ------- | ------- | --------- | ------------ | ---------- |
| `cohere-mini-50k-d768`  | 768D    | **300** | 0.772     | 3000 vectors | ✅ Success |
| `msmarco-mini-10k-d384` | 384D    | **400** | 0.673     | 5000 vectors | ✅ Success |
| `openai-ada-10k-d1536`  | 1536D   | **200** | 0.930     | 1000 vectors | ✅ Success |

#### **Memory Management Guidelines (8GB RAM Laptop)**

- **384D datasets**: `--limit_n 5000` (aman untuk kedua database)
- **768D datasets**: `--limit_n 5000` (Qdrant), `--limit_n 3000` (Weaviate)
- **1536D datasets**: `--limit_n 1000-2000` (kedua database)

#### **Key Findings Nomor 3**:

- **Qdrant 2x lebih cepat** secara konsisten (500-600 vs 200-400 QPS)
- **Semua test CPU-bound** - NVMe storage tidak menjadi bottleneck
- **Qdrant lebih stabil** across semua dimensi
- **Weaviate perlu memory limit lebih konservatif**

---

### **NOMOR 4: Sensitivitas terhadap Dimensi Embedding dan Ukuran Dataset**

**Konsep**: Analisis bagaimana performa database vektor berubah dengan dimensi embedding (384D, 768D, 1536D) dan ukuran dataset (10k-50k vektor). Dimensi tinggi meningkatkan kompleksitas komputasi dan memory usage, sementara dataset besar mempengaruhi I/O dan index size. Di laptop 8GB RAM, trade-off ini krusial untuk optimasi resource.

#### **Qdrant Sensitivity Results**

| Dataset                 | Dimensi | Ukuran | Recall@10 | Max QPS | CPU Usage | Memory Limit | Status       |
| ----------------------- | ------- | ------ | --------- | ------- | --------- | ------------ | ------------ |
| `msmarco-mini-10k-d384` | 384D    | 10k    | **0.845** | **600** | 141%      | 5000 vectors | ✅ Optimal   |
| `cohere-mini-50k-d768`  | 768D    | 50k    | **0.917** | **500** | 143%      | 5000 vectors | ✅ Stable    |
| `openai-ada-10k-d1536`  | 1536D   | 10k    | **0.939** | **600** | 130%      | 2000 vectors | ✅ Efficient |

#### **Weaviate Sensitivity Results**

| Dataset                 | Dimensi | Ukuran | Recall@10 | Max QPS | CPU Usage | Memory Limit | Status      |
| ----------------------- | ------- | ------ | --------- | ------- | --------- | ------------ | ----------- |
| `msmarco-mini-10k-d384` | 384D    | 10k    | **0.822** | **400** | 83%       | 5000 vectors | ✅ Good     |
| `cohere-mini-50k-d768`  | 768D    | 50k    | **0.772** | **300** | 81%       | 5000 vectors | ✅ Stable   |
| `openai-ada-10k-d1536`  | 1536D   | 10k    | **0.931** | **200** | 78%       | 2000 vectors | ✅ Balanced |

#### **Parameter ef Sensitivity Analysis**

**Qdrant ef_search Parameter Study**:

- **Low-dim (384D)**: Recall konsisten 0.845 across ef=64-256, QPS stabil 600
- **Medium-dim (768D)**: Recall konsisten 0.917 across ef=64-256, QPS stabil 500
- **High-dim (1536D)**: Recall konsisten 0.939 across ef=64-256, QPS stabil 600

**Weaviate ef Parameter Study**:

- **Low-dim (384D)**: Recall improves 0.572→0.822 (+44%) with ef=64→256, QPS 400 stable
- **Medium-dim (768D)**: Recall improves 0.644→0.880 (+37%) with ef=64→256, QPS 300 stable
- **High-dim (1536D)**: Recall improves 0.688→0.931 (+35%) with ef=64→256, QPS 200 stable

#### **Memory Management Guidelines (8GB RAM Laptop)**

| Dimensi   | Dataset Size | Qdrant Limit     | Weaviate Limit   | Reasoning             |
| --------- | ------------ | ---------------- | ---------------- | --------------------- |
| **384D**  | 10k-50k      | `--limit_n 5000` | `--limit_n 5000` | Low memory footprint  |
| **768D**  | 10k-50k      | `--limit_n 5000` | `--limit_n 3000` | Medium memory usage   |
| **1536D** | 10k          | `--limit_n 2000` | `--limit_n 2000` | High memory footprint |

#### **Key Findings Nomor 4**:

- **Qdrant lebih konsisten**: Performance stabil across semua dimensi, kurang sensitif terhadap parameter tuning
- **Weaviate lebih tunable**: Significant recall improvement (+35-44%) dengan ef tuning, tapi QPS lebih rendah
- **Dimensi impact**: 384D optimal untuk speed, 1536D untuk accuracy, 768D balanced
- **Memory critical**: High-dim datasets butuh limit konservatif untuk stability
- **CPU-bound everywhere**: Tidak ada I/O bottleneck di semua konfigurasi

#### **Performance Patterns by Dimension**:

- **384D (Low-dim)**: Qdrant 1.5x faster (600 vs 400 QPS), optimal untuk high-throughput
- **768D (Medium-dim)**: Qdrant 1.7x faster (500 vs 300 QPS), sweet spot untuk most applications
- **1536D (High-dim)**: Qdrant 3x faster (600 vs 200 QPS), significant gap pada high-accuracy scenarios

#### **Recommendations by Use Case**:

- **Speed-critical (real-time search)**: Qdrant + 384D dataset
- **Accuracy-critical (high-precision)**: Weaviate with ef=256 + 1536D dataset
- **Balanced performance**: Qdrant + 768D dataset
- **Resource-constrained**: Weaviate + 384D dataset dengan ef tuning

---

### Connection Errors

```bash
# Test connectivity
curl http://localhost:6333/healthz    # Qdrant
curl http://localhost:8080/v1/meta    # Weaviate

# Restart services
make down && sleep 5 && make up
```

### Sequential Benchmark Issues

```bash
# Pastikan hanya satu database yang running
docker compose ps

# Jika kedua database running, stop salah satu
docker compose stop weaviate  # Untuk benchmark Qdrant
# atau
docker compose stop qdrant && docker compose start weaviate  # Untuk benchmark Weaviate

# Check resource usage
docker stats
```

### Disk Space Issues

```bash
# Check usage
du -sh "$NVME_ROOT"
df -h .

# Clean up
make clean  # Remove all volumes
docker system prune -a  # Remove unused Docker data
```

---

## 📝 Output Format

### Benchmark Result

```json
[
  {
    "conc": 1,
    "qps": 28.5,
    "cpu": 55.2,
    "avg_bandwidth_mb_s": 0.1,
    "read_mb": 1.0,
    "write_mb": 0.4,
    "elapsed": 48.4
  }
]
```

### Analysis Summary

```json
{
  "max_qps": 600.0,
  "min_p99": null,
  "avg_cpu": 242.5,
  "avg_io_bandwidth_mb_s": 0.1,
  "bottleneck_analysis": "CPU-bound (high CPU usage)"
}
```

---

## 🎓 Research Documentation

### Environment Info

Dokumentasikan untuk reproducibility:

```bash
# System specs
uname -a
docker --version
docker compose version

# Hardware
# CPU: Intel Core i5, 1.4 GHz Quad-Core
# RAM: 8GB 2133 MHz LPDDR3
# Storage: NVMe SSD
# OS: macOS 15.6.1 (24G90)

# Configuration
cat bench/config.yaml
```

### Exclusion Statement

Untuk laporan/skripsi:

> "Milvus dikecualikan dari perbandingan karena keterbatasan resource hardware (8GB RAM) dan fokus pada HNSW-based comparison yang fair. Qdrant dan Weaviate dipilih karena sama-sama menggunakan HNSW sebagai index utama, memungkinkan apple-to-apple comparison dengan parameter yang comparable."

---

## 🔗 References

- **Paper Rujukan**: `paper_rujukan.pdf`
- **Batasan Studi**: `bab_1_2_3.txt`
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Weaviate Docs**: https://weaviate.io/developers/weaviate

---

## ❓ FAQ

**Q: Container stuck di "waiting" atau healthcheck gagal?**  
A: Biasanya karena `curl`/`wget` tidak tersedia di container. Restart dengan `make down && make up`. Jika masih gagal, cek logs dengan `docker compose logs qdrant` atau `docker compose logs weaviate`.

**Q: Apakah valid tanpa Milvus?**  
A: Ya! Fokus pada HNSW comparison (apple-to-apple), metodologi paper tetap diikuti.

**Q: Berapa lama total waktu eksekusi?**  
A: **Mode cepat (--quick5)**: ≤5 menit per database, ≤30 menit untuk semua skenario. **Mode lengkap**: 8-12 menit per dataset per database, ~1.5-2 jam untuk complete study 4 pertanyaan penelitian. Sequential untuk fairness!

**Q: Bagaimana cara menghemat waktu untuk eksplorasi awal?**  
A: Gunakan `--quick5` untuk verifikasi setup dan explore pattern. Setelah yakin, jalankan mode lengkap untuk data penelitian final.

**Q: Mengapa jalan satu per satu (sequential)?**  
A: Untuk fairness comparison! Jika paralel, kedua database berebut resource (CPU/RAM/I/O) sehingga hasil tidak akurat. Laptop/workstation resource terbatas.

**Q: Ada opsi mode cepat untuk testing?**  
A: Ya! Gunakan flag `--quick5` untuk benchmark ≤5 menit per database. Cocok untuk eksplorasi dan verifikasi setup sebelum menjalankan eksperimen lengkap.

**Q: Bagaimana cara menjalankan benchmark?**  
A: Gunakan `python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768`. Script otomatis menyimpan hasil ke folder `results/`. Jangan gunakan redirection `> file.json` karena script sudah menulis file sendiri.

**Q: Apa perbedaan utama Qdrant vs Weaviate?**  
A: Qdrant lebih cepat (125-500 QPS vs 125 QPS) dan lebih efisien untuk vector search murni. Weaviate lebih hemat CPU (70-85% vs 200-700%) tapi lebih lambat, dengan fitur hybrid search dan GraphQL yang lebih kaya.

**Q: Bisa tambah Milvus?**  
A: Jika punya hardware powerful (16GB+ RAM), uncomment di `docker-compose.yml`. Lebih stabil di Linux. Untuk laptop, fokus Qdrant vs Weaviate sudah representatif.

---

## 🔬 Panduan Step-by-Step: 4 Pertanyaan Penelitian Utama

Berikut adalah panduan lengkap untuk menjawab 4 pertanyaan penelitian utama melalui benchmark praktis. Setiap pertanyaan disertai penjelasan konseptual, langkah-langkah eksekusi spesifik, dan opsi mode cepat (≤5 menit) untuk eksperimen awal.

### ⚡ Mode Cepat vs Mode Lengkap

**Mode Cepat (--quick5)**: ≤5 menit per database, cocok untuk eksplorasi awal dan verifikasi setup.

- Concurrency: hanya 1 worker
- Repeats: maksimal 3×
- Run time: maksimal 8 detik per test
- ef range: terbatas 64-128

**Mode Lengkap**: 8-12 menit per database, untuk hasil penelitian final.

- Concurrency: 1-2 workers untuk uji skalabilitas
- Repeats: 5× untuk reliability
- Run time: 10 detik per test
- ef range: 64-256 untuk sensitivity study

### 1. Model Kueri dan Fitur Sistem (Payload Filtering vs Hybrid Search)

**Konsep**: Qdrant mendukung **payload filtering** untuk filter metadata saat pencarian vektor (misalnya, filter berdasarkan kategori dokumen), yang dapat meningkatkan akurasi hasil tapi menambah overhead CPU. Weaviate mendukung **hybrid search** yang menggabungkan pencarian vektor dengan teks keyword (BM25), memberikan fleksibilitas lebih tapi berpotensi menurunkan QPS karena kompleksitas query. Dalam pipeline PDF→embedding→vector DB, fitur ini memengaruhi throughput karena menambah computational load, terutama di lingkungan Docker NVMe single-node dengan resource terbatas.

**Langkah-langkah Benchmark**:

```bash
# Setup awal (wajib)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up
make bench-shell

# ===========================================
# STEP 1: Test Qdrant dengan Payload Filtering
# ===========================================
# Stop Weaviate untuk fairness (dari terminal host):
docker compose stop weaviate

# Jalankan benchmark Qdrant (di bench-shell):
# Mode cepat (≤5 menit, untuk eksplorasi awal):
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --quick5

# Mode lengkap (untuk hasil final):
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768

# ===========================================
# STEP 2: Test Weaviate dengan Hybrid Search
# ===========================================
# Switch ke Weaviate (dari terminal host):
docker compose stop qdrant && docker compose start weaviate

# Jalankan benchmark Weaviate (di bench-shell):
# Mode cepat:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --quick5

# Mode lengkap:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768

# ===========================================
# STEP 3: Analisis Perbandingan
# ===========================================
# Exit dari bench-shell dan analisis (dari host):
exit
python3 bench/analyze_results.py --results results/qdrant_cohere-mini-50k-d768.json results/weaviate_cohere-mini-50k-d768.json
```

**Metrik yang Diukur**:

- **QPS**: Throughput pencarian per detik
- **P99 Latency**: 99th percentile response time
- **CPU Usage**: Penggunaan CPU rata-rata
- **I/O Bandwidth**: Transfer data ke/dari storage

**Interpretasi Hasil**:

- Qdrant biasanya lebih efisien untuk vector search murni dengan payload filtering (higher QPS, lower CPU)
- Weaviate memberikan fleksibilitas hybrid tapi dengan overhead (trade-off performa vs fitur)

### 2. Penyetelan Parameter HNSW (ef_search vs ef)

**Konsep**: Parameter `ef` (exploration factor) mengontrol seberapa dalam algoritma HNSW mengeksplorasi kandidat tetangga untuk akurasi. Nilai ef tinggi meningkatkan recall@10 ≥0.9 tapi menurunkan QPS dan meningkatkan latency/CPU karena lebih banyak komputasi. Trade-off ini krusial di laptop: ef=64-128 optimal untuk balance, ef>256 overkill dan CPU-bound.

**Langkah-langkah Benchmark**:

```bash
# Setup awal
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up
make bench-shell

# ===========================================
# STEP 1: Sensitivity Study Qdrant (ef_search)
# ===========================================
# Stop Weaviate:
docker compose stop weaviate

# Test berbagai nilai ef_search untuk trade-off recall vs QPS:
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600

# ===========================================
# STEP 2: Sensitivity Study Weaviate (ef)
# ===========================================
# Switch ke Weaviate:
docker compose stop qdrant && docker compose start weaviate

# Test berbagai nilai ef:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600

# ===========================================
# STEP 3: Analisis Parameter Tuning
# ===========================================
exit
python3 bench/analyze_results.py --results results/qdrant_cohere-mini-50k-d768_sensitivity.json results/weaviate_cohere-mini-50k-d768_sensitivity.json
```

**Yang Diuji**:

- ef values: 64, 128, 192, 256
- Recall@10: harus ≥0.9 untuk fairness
- QPS vs ef: trade-off speed vs accuracy
- CPU usage vs ef: resource consumption
- **Budget**: 600 detik (10 menit) total untuk seluruh sensitivity study

**Penjelasan Parameter Budget**:

- **`--budget_s 600`**: Angka 600 detik = 10 menit total untuk seluruh sensitivity study
- **Mengapa perlu budget?**: Mencegah benchmark berjalan terlalu lama dan membatasi resource usage
- **Breakdown waktu**: 4 nilai ef × 5 repeats × 2 concurrency levels × 10 detik per test ≈ 400 detik (7 menit) + buffer
- **Fallback mechanism**: Jika waktu habis sebelum semua test selesai, benchmark akan berhenti dengan data yang sudah terkumpul

**Insight yang Diharapkan**:

- ef=128 sering optimal untuk laptop (balance recall ≥0.9 tanpa CPU bottleneck)
- Qdrant lebih responsif terhadap ef tuning dibanding Weaviate
- Diminishing returns setelah ef>192 di environment terbatas

### 3. Skalabilitas Konkurensi (1-2 Workers)

**Konsep**: Konkurensi 1-2 worker menguji skalabilitas awal. Di laptop, konkurensi rendah (1) menghindari contention, tapi 2 worker dapat mengungkap bottleneck CPU-bound (high CPU usage, low QPS gain) atau I/O-bound (high I/O wait, disk saturation). Monitor CPU >80% menunjukkan CPU-bound, I/O >100MB/s menunjukkan I/O-bound.

**Langkah-langkah Benchmark**:

```bash
# Setup awal
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up
make bench-shell

# ===========================================
# STEP 1: Test Skalabilitas Qdrant
# ===========================================
docker compose stop weaviate

# Test pada semua dataset untuk melihat sensitivitas terhadap dimensi:
# Baseline (low-dim, 384D):
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384

# Main (medium-dim, 768D) - GUNAKAN --limit_n 5000 jika memory limited:
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000

# Stress (high-dim, 1536D) - GUNAKAN --limit_n 2000 jika memory limited:
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536 --limit_n 2000

# ===========================================
# STEP 2: Test Skalabilitas Weaviate
# ===========================================
docker compose stop qdrant && docker compose start weaviate

# Test pada semua dataset:
python3 bench.py --db weaviate --index hnsw --dataset msmarco-mini-10k-d384
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000
python3 bench.py --db weaviate --index hnsw --dataset openai-ada-10k-d1536 --limit_n 2000

# ===========================================
# STEP 3: Analisis Bottleneck Detection
# ===========================================
exit
python3 bench/analyze_results.py --results results/qdrant_msmarco-mini-10k-d384.json results/qdrant_cohere-mini-50k-d768.json results/qdrant_openai-ada-10k-d1536.json results/weaviate_msmarco-mini-10k-d384.json results/weaviate_cohere-mini-50k-d768.json results/weaviate_openai-ada-10k-d1536.json
```

**Metrik Skalabilitas**:

- **QPS gain ratio**: QPS(concurrency=2) / QPS(concurrency=1)
- **CPU saturation**: rata-rata >80% = CPU-bound
- **I/O saturation**: bandwidth >100MB/s = I/O-bound
- **Latency penalty**: P99 increase dengan concurrency

**Interpretasi**:

- Ideal: QPS ratio ~1.8-2.0 (linear scaling)
- CPU-bound: QPS ratio <1.3, CPU >80%
- I/O-bound: QPS ratio <1.5, I/O >100MB/s
- Memory-bound: Sudden QPS drop

### 4. Sensitivitas Dimensi Embedding dan Dataset Size

**Konsep**: Dimensi embedding (384, 768, 1536) memengaruhi kompleksitas vektor: dimensi tinggi meningkatkan memory/CPU usage, menurunkan QPS. Ukuran dataset (10k-50k vektor) memengaruhi I/O dan index size. Di laptop, dimensi 1536D dengan 50k vektor sering I/O-bound, dimensi 384D lebih efisien.

**Langkah-langkah Benchmark**:

```bash
# Setup awal
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up
make bench-shell

# ===========================================
# STEP 1: Matrix Testing Qdrant
# ===========================================
docker compose stop weaviate

# Low-dimension baseline (cepat, hemat resource):
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384

# Medium-dimension main test (representatif paper rujukan):
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000

# High-dimension stress test (uji batas sistem):
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536 --limit_n 2000

# ===========================================
# STEP 2: Matrix Testing Weaviate
# ===========================================
docker compose stop qdrant && docker compose start weaviate

python3 bench.py --db weaviate --index hnsw --dataset msmarco-mini-10k-d384
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000
python3 bench.py --db weaviate --index hnsw --dataset openai-ada-10k-d1536 --limit_n 2000

# ===========================================
# STEP 3: Comprehensive Analysis
# ===========================================
exit
python3 bench/analyze_results.py --results results/qdrant_msmarco-mini-10k-d384.json results/qdrant_cohere-mini-50k-d768.json results/qdrant_openai-ada-10k-d1536.json results/weaviate_msmarco-mini-10k-d384.json results/weaviate_cohere-mini-50k-d768.json results/weaviate_openai-ada-10k-d1536.json
```

**Dimensi vs Performance Matrix**:

| Dataset | Dimensi | Size | Tujuan        | Expected QPS | CPU Load |
| ------- | ------- | ---- | ------------- | ------------ | -------- |
| msmarco | 384D    | 10k  | Baseline fast | ~40-60       | Low      |
| cohere  | 768D    | 50k  | Main test     | ~25-35       | Medium   |
| openai  | 1536D   | 10k  | Stress test   | ~15-25       | High     |

**Insight yang Diharapkan**:

- **384D**: Efficient, cocok untuk aplikasi speed-critical
- **768D**: Balanced, optimal untuk most use cases
- **1536D**: Resource-intensive, butuh hardware powerful

**Performance Degradation Pattern**:

- Qdrant: lebih linear degradation dengan dimensi
- Weaviate: steeper degradation pada high-dim
- Dataset size: mempengaruhi I/O lebih dari CPU

---

## ⏱️ Estimasi Waktu Eksekusi

### Mode Cepat (--quick5)

| Skenario            | Per Database | Total     |
| ------------------- | ------------ | --------- |
| Single dataset test | ≤5 menit     | ≤10 menit |
| All datasets (3×)   | ≤15 menit    | ≤30 menit |
| Sensitivity study   | ≤8 menit     | ≤16 menit |

### Mode Lengkap

| Skenario                              | Per Database    | Total         |
| ------------------------------------- | --------------- | ------------- |
| Single dataset test                   | 8-12 menit      | 16-24 menit   |
| All datasets (3×)                     | 25-35 menit     | 50-70 menit   |
| Sensitivity study                     | 15-20 menit     | 30-40 menit   |
| **Complete study (semua pertanyaan)** | **45-60 menit** | **1.5-2 jam** |

### Rekomendasi Workflow untuk Penelitian

#### Phase 1: Eksplorasi Cepat (≤30 menit total)

```bash
# Verifikasi setup dan pattern awal dengan mode cepat
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up
make bench-shell

# Test cepat untuk validasi
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --quick5
docker compose stop qdrant && docker compose start weaviate
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 --quick5
```

#### Phase 2: Data Collection Lengkap (1.5-2 jam total)

```bash
# Jalankan semua 4 pertanyaan penelitian dengan mode lengkap
# Ikuti langkah-langkah detail di section "4 Pertanyaan Penelitian Utama"
```

#### Phase 3: Analysis & Visualization

```bash
exit
python3 bench/analyze_results.py --results results_*.json
```

---

## �📞 Support

**Pre-flight Check**:

```bash
./test_setup.sh  # Run automated checks
```

**Get Help**:

```bash
make help  # Show all commands
python3 bench.py --help  # Benchmark options
```

---

**Happy Benchmarking! 🚀**

_Last updated: October 22, 2025_
