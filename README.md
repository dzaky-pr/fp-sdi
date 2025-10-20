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

# Check disk space (REQUIRED)
df -h .  # Minimal 10GB free
```

### Setup

```bash
# 1. Clone repository
git clone https://github.com/dzaky-pr/fp-sdi.git
cd fp-sdi

# 2. Setup NVMe storage path (KRITIS - HARUS sesuai!)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
mkdir -p "$NVME_ROOT"

# Verify path (HARUS output: /Users/dzakyrifai/nvme-vdb)
echo "$NVME_ROOT"

# 3. Build containers
make build

# 4. Start services (gunakan export NVME_ROOT jika belum permanent)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb" && make up

# 5. Verify setup
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
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 > /app/results_qdrant.json

# ===========================================
# RUN WEAVIATE BENCHMARK (Stop Qdrant first)
# ===========================================
# From host terminal (bukan di bench-shell):
docker compose stop qdrant && docker compose start weaviate

# Then in bench-shell:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 > /app/results_weaviate.json

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
python3 bench/analyze_results.py results_qdrant_baseline.json results_weaviate_baseline.json results_qdrant.json results_weaviate.json results_qdrant_stress.json results_weaviate_stress.json
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
- macOS (Apple Silicon) or Linux

### 2. NVMe Storage Setup

⚠️ **KRITIS**: Path HARUS `/Users/dzakyrifai/nvme-vdb` (sesuai hardware MacBook Pro M1)

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

### 3. Build & Start Services

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

### 4. Run Benchmarks

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
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 > /app/results_qdrant.json
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384 > /app/results_qdrant_baseline.json
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536 > /app/results_qdrant_stress.json

# ===========================================
# WEAVIATE BENCHMARKS
# ===========================================
# Stop Qdrant & start Weaviate (dari terminal host):
docker compose stop qdrant && docker compose start weaviate

# Jalankan benchmarks Weaviate (di bench-shell):
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768 > /app/results_weaviate.json
python3 bench.py --db weaviate --index hnsw --dataset msmarco-mini-10k-d384 > /app/results_weaviate_baseline.json
python3 bench.py --db weaviate --index hnsw --dataset openai-ada-10k-d1536 > /app/results_weaviate_stress.json

# Optional: Sensitivity study (recall vs QPS trade-off)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --sensitivity > /app/results_qdrant_sensitivity.json

# Exit
exit
```

**Mengapa Sequential?**

- **Fairness**: Setiap database dapat full resource (CPU, RAM, I/O)
- **Accuracy**: Tidak ada interference antar database
- **Reliability**: Benchmark lebih stabil dan reproducible
- **Resource Efficiency**: Laptop/workstation terbatas resource

### 5. Analyze Results

```bash
# Compare results
python3 bench/analyze_results.py results_qdrant.json results_weaviate.json

# Generate plots (optional)
python3 bench/analyze_results.py results_qdrant.json results_weaviate.json --plot
```

---

## 📊 Expected Performance

Berdasarkan testing di MacBook Pro M1 (16GB RAM) dengan dataset `cohere-mini-50k-d768` (50k vectors, 768D). **Benchmark dijalankan sequential** (satu database aktif) untuk fairness.

### Qdrant

```
Concurrency=1: ~28 QPS, P99 ~42ms, recall ≥0.9
Concurrency=2: ~45 QPS, P99 ~55ms
CPU: 40-60%, I/O: 50-100 MB/s
```

### Weaviate

```
Concurrency=1: ~24 QPS, P99 ~48ms, recall ≥0.9
Concurrency=2: ~38 QPS, P99 ~65ms
CPU: 50-70%, I/O: 60-120 MB/s
```

### Trade-offs

| Aspect        | Qdrant            | Weaviate               |
| ------------- | ----------------- | ---------------------- |
| **QPS**       | ⚡ Higher         | Lower                  |
| **Latency**   | ⚡ Lower P99      | Higher P99             |
| **Memory**    | More efficient    | Higher usage           |
| **Features**  | Payload filtering | Hybrid search, GraphQL |
| **Ecosystem** | Python-first      | Multi-language         |

---

## 🛠️ Configuration

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
# Basic benchmark (main dataset)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768

# Benchmark on different datasets
python3 bench.py --db qdrant --index hnsw --dataset msmarco-mini-10k-d384    # Baseline (low-dim)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768     # Main (medium-dim)
python3 bench.py --db qdrant --index hnsw --dataset openai-ada-10k-d1536     # Stress (high-dim)

# Sensitivity study
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
{
  "results": [
    {
      "concurrency": 1,
      "qps": 28.5,
      "p99": 42.3,
      "recall": 0.92,
      "cpu": 55.2,
      "param": { "ef": 128 }
    }
  ],
  "metadata": {
    "db": "qdrant",
    "index": "hnsw",
    "dataset": "cohere-mini-50k-d768",
    "timestamp": "2025-01-19T..."
  }
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
# CPU: Apple M1, 8 cores
# RAM: 16GB
# Storage: NVMe SSD 500GB
# OS: macOS Sonoma 14.5

# Configuration
cat bench/config.yaml
```

### Exclusion Statement

Untuk laporan/skripsi:

> "Milvus dikecualikan dari perbandingan karena keterbatasan resource hardware (16GB RAM) dan fokus pada HNSW-based comparison yang fair. Qdrant dan Weaviate dipilih karena sama-sama menggunakan HNSW sebagai index utama, memungkinkan apple-to-apple comparison dengan parameter yang comparable."

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

**Q: Berapa lama total waktu?**  
A: ~8-12 menit per dataset per database. Total untuk semua dataset: ~1-1.5 jam. Sequential untuk fairness!

**Q: Mengapa jalan satu per satu?**  
A: Untuk fairness comparison! Jika paralel, kedua database berebut resource (CPU/RAM/I/O) sehingga hasil tidak akurat. Laptop/workstation resource terbatas.

**Q: Bisa pakai custom embeddings?**  
A: Ya, gunakan `--embeddings_npy` dan `--queries_npy`.

**Q: Apa perbedaan utama Qdrant vs Weaviate?**  
A: Qdrant lebih cepat (higher QPS, lower latency), Weaviate lebih feature-rich (hybrid search, GraphQL).

**Q: Bisa tambah Milvus?**  
A: Jika punya hardware powerful (16GB+ RAM), uncomment di `docker-compose.yml`. Lebih stabil di Linux.

---

## 📞 Support

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

_Last updated: October 20, 2025_
