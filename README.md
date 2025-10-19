# Vector Database Benchmark: Qdrant vs Weaviate

> Perbandingan performa Qdrant vs Weaviate untuk semantic search pada dokumen PDF, mengikuti metodologi paper rujukan dengan fokus pada HNSW-based comparison.

## 📊 Overview

### Mengapa Hanya Qdrant vs Weaviate?

**Milvus dikecualikan** karena:

- Resource-intensive (butuh 8GB+ RAM)
- Unstable di macOS/laptop (sering crash)
- API kompleks dan sering berubah
- **Fokus apple-to-apple**: Qdrant & Weaviate sama-sama pakai HNSW

### Validitas Penelitian

| Aspek          | Qdrant              | Weaviate               | Status        |
| -------------- | ------------------- | ---------------------- | ------------- |
| **Index**      | HNSW                | HNSW                   | ✅ Sama       |
| **Deployment** | Docker              | Docker                 | ✅ Sama       |
| **Storage**    | NVMe                | NVMe                   | ✅ Sama       |
| **Tuning**     | ef, M, ef_construct | ef, maxConnections, ef | ✅ Comparable |

**Sesuai Paper Rujukan**:

- ✅ Single-machine Docker setup
- ✅ NVMe storage dengan dedicated volumes
- ✅ Standardized metrics (QPS, P99 latency, recall@10)
- ✅ Fair parameter tuning hingga recall ≥ 0.9
- ✅ Multiple runs (5× repeats) untuk reliability

**Sesuai Batasan Studi (Bab 1-3)**:

- ✅ Docker-based only (LanceDB dikecualikan)
- ✅ Laptop/workstation environment
- ✅ HNSW focus (Milvus IVF/DiskANN tidak diperlukan)

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
- **Detail**: Menghasilkan embedding dari PDF menggunakan SentenceTransformers (gratis dan open source), atau data synthetic. Mendukung hybrid search dengan sparse vectors (BM25). Cache dataset ke file .npy untuk efisiensi.

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

# 2. Setup NVMe storage path
export NVME_ROOT="$HOME/nvme-vdb"
mkdir -p "$NVME_ROOT"

# 3. Build containers
make build

# 4. Start services
make up

# 5. Verify setup
make test-all
```

### Run Benchmarks

```bash
# Enter benchmark container
make bench-shell

# Run Qdrant
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 > /app/results_qdrant.json

# Run Weaviate
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-200k-d768 > /app/results_weaviate.json

# Exit
exit

# Analyze results
python3 bench/analyze_results.py results_qdrant.json results_weaviate.json
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

⚠️ **PENTING**: Gunakan path yang AMAN!

```bash
# AMAN - di user directory
export NVME_ROOT="$HOME/nvme-vdb"
mkdir -p "$NVME_ROOT"

# Verify
echo "$NVME_ROOT"  # Should show: /Users/username/nvme-vdb
ls -la "$NVME_ROOT"

# Make permanent (optional)
echo 'export NVME_ROOT="$HOME/nvme-vdb"' >> ~/.zshrc
```

❌ **JANGAN gunakan**:

- `/System/*` - System files
- `/usr/*` - System binaries
- `/` - Root filesystem

### 3. Build & Start Services

```bash
# Build benchmark container
make build

# Start Qdrant + Weaviate
make up

# Check services
docker compose ps
# Expected: qdrant (healthy), weaviate (healthy), bench (up)

# Test connectivity
make test-all
```

### 4. Run Benchmarks

```bash
# Enter container
make bench-shell

# Inside container - run benchmarks
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 > /app/results_qdrant.json
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-200k-d768 > /app/results_weaviate.json

# Optional: Sensitivity study (recall vs QPS trade-off)
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 --sensitivity > /app/results_qdrant_sensitivity.json

# Exit
exit
```

### 5. Analyze Results

```bash
# Compare results
python3 bench/analyze_results.py results_qdrant.json results_weaviate.json

# Generate plots (optional)
python3 bench/analyze_results.py results_qdrant.json results_weaviate.json --plot
```

---

## 📊 Expected Performance

Berdasarkan testing di MacBook Pro M1 (16GB RAM):

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

Edit `bench/config.yaml`:

```yaml
datasets:
  - name: cohere-mini-200k-d768
    n_vectors: 25000 # Reduce for faster testing
    n_queries: 1000
    dim: 768
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

### Benchmark Options

```bash
# Basic benchmark
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768

# Sensitivity study
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 --sensitivity

# I/O baseline test
python3 bench.py --baseline

# Custom embeddings
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 --embeddings_npy path/to/custom.npy
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
curl http://localhost:8080/v1/.well-known/ready  # Weaviate

# Restart services
make down && sleep 5 && make up
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
    "dataset": "cohere-mini-200k-d768",
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

**Q: Apakah valid tanpa Milvus?**  
A: Ya! Fokus pada HNSW comparison (apple-to-apple), metodologi paper tetap diikuti.

**Q: Berapa lama total waktu?**  
A: ~15-20 menit per database, total ~30-40 menit.

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

_Last updated: January 19, 2025_
