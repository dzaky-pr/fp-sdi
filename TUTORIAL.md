# Tutorial Lengkap: Benchmarking Vector Databases untuk Semantic Search Dokumen PDF

## 📋 Daftar Isi

1. [Persiapan Sistem](#persiapan-sistem)
2. [Setup NVMe Internal (CRITICAL)](#setup-nvme-internal)
3. [Setup Codebase](#setup-codebase)
4. [Final Check - Semua Siap?](#final-check)
5. [Menjalankan Benchmark](#menjalankan-benchmark)
6. [Troubleshooting](#troubleshooting)
7. [Cleanup & Data Management](#cleanup--data-management)
8. [Additional Resources & References](#additional-resources--references)
9. [FAQ](#faq)

Tutorial ini memandu Anda **step-by-step** untuk menjalankan benchmarking vector databases sesuai metodologi paper rujukan, namun disesuaikan untuk laptop dengan Docker. **IKUTI URUTAN DENGAN BENAR** untuk menghindari masalah!

---

## 📦 Persiapan Sistem

### 🔍 Cek Prerequisites Wajib

**JALANKAN COMMAND INI SATU PER SATU:**

```bash
# 1. Cek Docker (WAJIB)
docker --version
# ✅ Expected: Docker version 24.0.6 atau lebih baru
# ❌ Error: command not found → Install Docker Desktop

docker compose version
# ✅ Expected: Docker Compose version v2.23.0 atau lebih baru
# ❌ Error: command not found → Update Docker Desktop

# 2. Cek Python (Opsional untuk analisis)
python3 --version
# ✅ Expected: Python 3.8.0 atau lebih baru
# ❌ Error: command not found → Install Python

# 3. Cek fio (Opsional untuk I/O baseline)
fio --version
# ✅ Expected: fio-3.41 atau versi lain
# ❌ Error: command not found → Install fio

# 4. Cek disk space (WAJIB)
df -h .
# ✅ Expected: Minimal 10GB free space
# ❌ Kurang space → Bersihkan disk
```

### 🛠️ Install yang Belum Ada

#### Docker Desktop (WAJIB)

```bash
# macOS - Install Docker Desktop
open https://www.docker.com/products/docker-desktop

# Setelah install, start Docker Desktop
# Tunggu hingga Docker whale icon di menu bar berwarna normal (tidak animasi)

# Test Docker berjalan
docker run hello-world
# ✅ Expected: "Hello from Docker!" message
```

#### Python 3 (Opsional)

```bash
# macOS - Install Python
brew install python
# atau download dari python.org

# Verifikasi
python3 --version
```

#### fio (Opsional)

```bash
# macOS - Install fio untuk I/O testing
brew install fio

# Verifikasi
fio --version
```

---

## ⚠️ Setup NVMe Internal (CRITICAL - BACA PERINGATAN!)

### 🚨 PERINGATAN KEAMANAN PENTING

**SALAH SETTING BISA MERUSAK/MENGHAPUS DATA LAPTOP ANDA!**

❌ **JANGAN PERNAH** gunakan path sistem:

- `/System/*` - SISTEM macOS PENTING
- `/usr/*` - PROGRAM SISTEM
- `/bin/*` - BINARY SISTEM
- `/Library/*` - LIBRARY SISTEM
- `/private/*` - DATA SISTEM SENSITIF
- `/` - ROOT FILESYSTEM
- `/nvme` - ROOT LEVEL BERBAHAYA

✅ **HANYA gunakan path di user directory:**

- `/Users/$(whoami)/nvme-vdb` ← RECOMMENDED
- `/Users/$(whoami)/Documents/vector-storage` ← AMAN
- `/Users/$(whoami)/Desktop/benchmark-data` ← AMAN

### 🛡️ Setup NVMe Internal yang AMAN

**IKUTI COMMAND INI DENGAN BENAR:**

```bash
# STEP 1: Buat folder NVMe internal di user directory (AMAN)
mkdir -p /Users/$(whoami)/nvme-vdb

# STEP 2: Verifikasi folder terbuat dengan benar
ls -la /Users/$(whoami)/nvme-vdb
# ✅ Expected: drwxr-xr-x ... /Users/username/nvme-vdb
# ❌ Error: Permission denied → Check user permissions

# STEP 3: Set environment variable PERMANENT di ~/.zshrc
echo 'export NVME_ROOT="/Users/$(whoami)/nvme-vdb"' >> ~/.zshrc

# STEP 4: Apply untuk session saat ini
export NVME_ROOT="/Users/$(whoami)/nvme-vdb"

# STEP 5: Verifikasi environment variable
echo "NVME_ROOT: $NVME_ROOT"
# ✅ Expected: NVME_ROOT: /Users/username/nvme-vdb
# ❌ Empty → Ulangi step 3-4

# STEP 6: Test Docker dapat akses folder (CRITICAL TEST)
docker run --rm -v "$NVME_ROOT:/test" alpine ls -la /test
# ✅ Expected: total 0 (folder kosong)
# ❌ Error: invalid mount → Check Docker Desktop settings

# STEP 7: Verifikasi setup final
du -sh "$NVME_ROOT"
# ✅ Expected: 0B atau ukuran kecil
# ❌ Error: No such file → Ulangi dari step 1
```

### ❓ FAQ: Mengapa `df -h | grep nvme` Tidak Menunjukkan Hasil?

**INI NORMAL** untuk NVMe Internal Setup!

- **NVMe External**: `df -h | grep nvme` menunjukkan drive terpisah
- **NVMe Internal**: Hanya folder di macOS filesystem, bukan mount terpisah
- **Setup BENAR** jika:
  ```bash
  echo "$NVME_ROOT"     # Shows: /Users/username/nvme-vdb
  ls -la "$NVME_ROOT"   # Shows: folder exists
  du -sh "$NVME_ROOT"   # Shows: size (0B atau ada data)
  ```

### 🔒 Double Check Keamanan

```bash
# PASTIKAN path AMAN - HARUS dalam /Users/
echo "$NVME_ROOT" | grep "^/Users/"
# ✅ Expected: /Users/username/nvme-vdb
# ❌ No output → PATH BERBAHAYA! Ulangi setup

# PASTIKAN tidak menggunakan path sistem berbahaya
echo "$NVME_ROOT" | grep -E "^/(System|usr|bin|Library|private|$)"
# ✅ Expected: No output (grep tidak menemukan apa-apa)
# ❌ Found match → PATH BERBAHAYA! Segera ubah
```

---

## 📁 Setup Codebase

### 1. Clone Repository

```bash
# Clone project repository
git clone https://github.com/dzaky-pr/fp-sdi.git
cd fp-sdi

# Verifikasi struktur project
ls -la
# ✅ Expected: Makefile, docker-compose.yml, bench/, datasets/, TUTORIAL.md
# ❌ Missing files → Clone ulang atau download manual
```

### 2. Setup Virtual Environment (Opsional - untuk analisis di host)

```bash
# Buat virtual environment untuk Python packages
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install packages untuk analisis hasil
pip install matplotlib pandas numpy scipy

# Test import packages
python3 -c "import matplotlib, pandas, numpy, scipy; print('All packages OK')"
# ✅ Expected: All packages OK
# ❌ Error → Install ulang packages

# Deactivate venv (optional)
# deactivate
```

### 3. Build Benchmark Container

```bash
# Build container untuk benchmarking
docker compose build bench
# ⏱️ Expected time: 5-10 menit
# ✅ Expected: Successfully tagged fp-sdi-bench
# ❌ Error → Check Docker daemon running

# Verifikasi container ter-build
docker images | grep fp-sdi-bench
# ✅ Expected: fp-sdi-bench latest
# ❌ No output → Build ulang container
```

### 4. Test Container Basic Functionality

```bash
# Test container dapat berjalan
docker compose run --rm bench python3 --version
# ✅ Expected: Python 3.13.0 (atau versi lain)
# ❌ Error → Check container build

# Test benchmark script exists
docker compose run --rm bench ls -la bench.py
# ✅ Expected: -rw-r--r-- ... bench.py
# ❌ No such file → Check project structure
```

---

## ✅ Final Check - Semua Siap?

**JALANKAN CHECKLIST INI SEBELUM MULAI BENCHMARK:**

### 🔍 System Check

```bash
# 1. Docker berjalan normal
docker ps
# ✅ Expected: Container list (bisa kosong)
# ❌ Error → Start Docker Desktop

# 2. NVME_ROOT environment variable set
echo "NVME_ROOT: $NVME_ROOT"
# ✅ Expected: /Users/username/nvme-vdb
# ❌ Empty → Ulangi NVMe setup

# 3. NVME folder accessible
ls -la "$NVME_ROOT"
# ✅ Expected: drwxr-xr-x ... folder info
# ❌ Error → Check folder permissions

# 4. Docker dapat akses NVME folder
docker run --rm -v "$NVME_ROOT:/test" alpine touch /test/docker-test.txt
ls -la "$NVME_ROOT/docker-test.txt"
# ✅ Expected: File terbuat
# ❌ Error → Check Docker volume mounting

# Cleanup test file
rm -f "$NVME_ROOT/docker-test.txt"
```

### 🐳 Container Check

```bash
# 5. Bench container image ready
docker images | grep fp-sdi-bench
# ✅ Expected: fp-sdi-bench image listed
# ❌ No image → Run docker compose build bench

# 6. Container dapat start dan akses tools
docker compose run --rm bench which python3 fio
# ✅ Expected: /usr/local/bin/python3, /usr/bin/fio
# ❌ Missing tools → Rebuild container
```

### 📊 Disk Space Check

```bash
# 7. Sufficient disk space
df -h .
# ✅ Expected: 10GB+ available space
# ❌ Insufficient → Free up disk space

df -h "$NVME_ROOT"
# ✅ Expected: Available space for data storage
# ❌ No space → Check disk usage
```

### 🌐 Network Check

```bash
# 8. Internet connection for Docker pulls
curl -s --max-time 5 https://registry-1.docker.io/v2/ > /dev/null && echo "Registry accessible" || echo "Network issue"
# ✅ Expected: Registry accessible
# ❌ Network issue → Check internet connection
```

### 🎯 Final Status

**Jika SEMUA check di atas ✅ PASSED:**

```bash
echo "🎉 SYSTEM READY FOR BENCHMARKING!"
echo "📍 NVME_ROOT: $NVME_ROOT"
echo "📊 Container: $(docker images --format '{{.Repository}}:{{.Tag}}' | grep fp-sdi-bench)"
echo "💾 Available space: $(df -h . | tail -1 | awk '{print $4}')"
```

**Jika ada yang ❌ FAILED:**

- Kembali ke bagian yang gagal
- Ikuti troubleshooting di bawah
- Jangan lanjut ke benchmark sebelum semua fix

---

## 🚀 Menjalankan Benchmark

### Metodologi Sesuai Paper Rujukan

Benchmarking mengikuti metodologi paper rujukan dengan adaptasi untuk laptop:

- **Dataset**: 50k vektor (vs 200k+ di server) - dimensi 768/1536
- **Duration**: 10 detik per run (vs 30 detik) - untuk testing cepat
- **Repeats**: 5 ulangan untuk rata-rata stabil
- **Target**: Recall@10 ≥ 0.9 dengan parameter tuning
- **Vector Databases**: Qdrant, Weaviate, Milvus (Docker only)
- **Metrics**: QPS, P50/P95/P99 latency, I/O bandwidth

### 🗂️ Urutan Testing (IKUTI STEP BY STEP)

#### STEP 1: I/O Baseline Test

**Tujuan**: Ukur performa disk sebagai baseline comparison

```bash
# Start benchmark container
docker compose --profile bench up -d bench

# Tunggu container ready
sleep 5
docker compose ps
# ✅ Expected: bench container "Up" status

# Jalankan I/O baseline test
docker compose exec bench python3 bench.py --baseline
```

**Expected Output**:

```json
{
  "random_4k_read": {
    "read_iops": 2146.73,
    "read_bw_mb": 8.38,
    "read_latency_us": 463.4
  },
  "sequential_read": {
    "read_iops": 864.97,
    "read_bw_mb": 864.97
  },
  "random_4k_write": {
    "write_iops": 5208.19,
    "write_bw_mb": 20.34
  }
}
```

**❌ Troubleshooting**:

- Error "No such file" → Container belum ready, tunggu lebih lama
- Error "fio timeout" → Disk terlalu lambat, normal untuk beberapa sistem

#### STEP 2: Test dengan Qdrant (Paling Stabil)

**Tujuan**: Test dengan vector database paling stabil untuk memastikan setup benar

```bash
# Start Qdrant + Bench containers
docker compose --profile bench --profile qdrant up -d qdrant bench

# Tunggu Qdrant ready
sleep 10
curl -s http://localhost:6333/healthz
# ✅ Expected: "healthz check passed"

# Jalankan benchmark Qdrant (akan auto-generate dataset synthetic)
docker compose exec bench python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 > results_qdrant.json

# Monitor progress - lihat log real-time
docker compose logs -f bench
```

**Expected Output Progress**:

```
Generating synthetic dataset
[qdrant][hnsw] tuned ef_search=64
[qdrant] conc=1 qps=29.2 p99=307.8ms cpu=0.0%
[qdrant] conc=2 qps=83.2 p99=70.6ms cpu=0.0%
```

**Expected Final Result** (`cat results_qdrant.json`):

```json
[
  {
    "conc": 1,
    "qps": 29.2,
    "p50": 37.1,
    "p99": 307.8,
    "cpu": 0.0
  },
  {
    "conc": 2,
    "qps": 83.2,
    "p50": 21.0,
    "p99": 70.6,
    "cpu": 0.0
  }
]
```

**✅ Success Indicators**:

- Dataset auto-generated di `./datasets/cohere-mini-200k-d768/`
- QPS > 20 dan meningkat dengan concurrency
- P99 latency < 500ms
- No error messages

#### STEP 3: Test dengan Weaviate

```bash
# Stop Qdrant, start Weaviate
docker compose down
docker compose --profile bench --profile weaviate up -d weaviate bench

# Tunggu Weaviate ready
sleep 15
curl -s http://localhost:8080/v1/.well-known/ready
# ✅ Expected: {"status": "ok"}

# Test Weaviate benchmark
docker compose exec bench python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-200k-d768 > results_weaviate.json

# Check results
cat results_weaviate.json
```

#### STEP 4: Test dengan Milvus (Optional - bisa unstable di macOS)

```bash
# Stop Weaviate, start Milvus
docker compose down
docker compose --profile bench --profile milvus up -d milvus bench

# Tunggu Milvus ready (lebih lama)
sleep 20
curl -s http://localhost:9091/healthz
# ✅ Expected: success response

# Test Milvus benchmark
docker compose exec bench python3 bench.py --db milvus --index hnsw --dataset cohere-mini-200k-d768 > results_milvus.json
```

**⚠️ Milvus Notes**:

- Milvus paling resource-intensive
- Sering crash di macOS dengan RAM < 8GB
- Jika gagal, focus ke Qdrant + Weaviate saja

#### STEP 5: Sensitivity Study (Parameter Tuning)

**Tujuan**: Test berbagai parameter untuk optimal performance

```bash
# Jalankan sensitivity study untuk Qdrant
docker compose --profile bench --profile qdrant up -d qdrant bench
docker compose exec bench python3 bench.py --sensitivity --db qdrant --index hnsw --dataset cohere-mini-200k-d768 > sensitivity_qdrant.json

# Check parameter vs performance relationship
cat sensitivity_qdrant.json
```

**Expected Output**:

```json
[
  {"param": {"ef": 16}, "recall": 0.85, "results": [...]},
  {"param": {"ef": 32}, "recall": 0.90, "results": [...]},
  {"param": {"ef": 64}, "recall": 0.92, "results": [...]}
]
```

### 📊 Analisis Hasil

#### Option 1: Analisis di Host (dengan Python)

```bash
# Activate virtual environment
source venv/bin/activate

# Generate plots dan summary
python3 bench/analyze_results.py --results results_qdrant.json --output results/

# Check generated files
ls -la results/
# Expected: *.png plots + summary.json
```

#### Option 2: Manual Analysis

```bash
# Compare QPS across databases
echo "=== QPS Comparison ==="
jq '.[0].qps' results_qdrant.json
jq '.[0].qps' results_weaviate.json
jq '.[0].qps' results_milvus.json

# Compare P99 latency
echo "=== P99 Latency Comparison ==="
jq '.[0].p99' results_qdrant.json
jq '.[0].p99' results_weaviate.json
jq '.[0].p99' results_milvus.json
```

### 🎯 Expected Results Summary

**Typical Performance Ranges** (50k vectors, laptop):

| Database | QPS (conc=1) | QPS (conc=2) | P99 Latency | Stability  |
| -------- | ------------ | ------------ | ----------- | ---------- |
| Qdrant   | 25-35        | 70-90        | < 400ms     | ⭐⭐⭐⭐⭐ |
| Weaviate | 20-30        | 50-70        | < 500ms     | ⭐⭐⭐⭐   |
| Milvus   | 30-40        | 80-100       | < 300ms     | ⭐⭐⭐     |

**Success Criteria**:

- ✅ QPS > 20 di concurrency=1
- ✅ QPS increase dengan concurrency
- ✅ P99 latency < 1000ms
- ✅ No crashes atau timeouts
- ✅ Dataset 1.4GB generated successfully

---

## 🛠️ Troubleshooting Common Issues

### 🚨 Critical Issues (SOLVE IMMEDIATELY)

#### ❌ ERROR: "No such file or directory" untuk bench.py

**Problem**: Script dijalankan dari host, bukan container

**Solution**:

```bash
# ❌ SALAH - dari host
python3 bench.py --db qdrant

# ✅ BENAR - dari dalam container
docker compose exec bench python3 bench.py --db qdrant
```

#### ❌ ERROR: "externally-managed-environment"

**Problem**: Python PEP 668 di macOS mencegah pip system install

**Solution**:

```bash
# Gunakan virtual environment di host (bukan container)
python3 -m venv venv
source venv/bin/activate
pip install -r bench/requirements.txt

# JANGAN PERNAH gunakan --break-system-packages!
```

#### ❌ ERROR: Docker Desktop "No such file or directory"

**Problem**: NVME_ROOT path tidak di-share ke Docker

**Solution**:

```bash
# 1. Check Docker Desktop Settings > Resources > File Sharing
# 2. Add your NVME_ROOT path manually
# 3. Apply & Restart Docker Desktop

# Verify path sharing works:
docker run --rm -v "$NVME_ROOT:/test" alpine ls /test
# Should work without errors
```

### ⚠️ Performance Issues

#### 🐌 QPS sangat rendah (< 10)

**Possible Causes & Solutions**:

1. **Resource Contention**:

```bash
# Check if multiple VDB running
docker compose ps
# Stop all except one
docker compose down
docker compose --profile bench --profile qdrant up -d qdrant bench
```

2. **Dataset Problem**:

```bash
# Re-generate synthetic dataset
rm -rf datasets/cohere-mini-200k-d768/
docker compose exec bench python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768
```

3. **Storage Bottleneck**:

```bash
# Check disk space
df -h "$NVME_ROOT"
# Expected: At least 5GB free

# Test I/O baseline
docker compose exec bench python3 bench.py --baseline
# Expected: Read IOPS > 1000
```

#### 🔥 Container Crashes / OOM

**Problem**: Insufficient memory for VDB + benchmark

**Solutions**:

1. **Reduce dataset size**:

```bash
# Edit bench/config.yaml
n_vectors: 25000  # Reduce from 50000
```

2. **Lower concurrency**:

```bash
# Edit bench/config.yaml
concurrency_grid: [1, 2, 4]  # Remove higher values
```

3. **Single VDB only**:

```bash
# Never run multiple VDB simultaneously
docker compose --profile bench --profile qdrant up -d
# NOT: --profile milvus --profile weaviate at same time
```

### 🔌 Container Connection Issues

#### ❌ Qdrant: "Connection refused localhost:6333"

```bash
# Check health status
docker compose ps
# Expected: qdrant container "healthy"

# Check logs
docker compose logs qdrant
# Look for "Actix server started"

# Test connection
curl -s http://localhost:6333/healthz
# Expected: "healthz check passed"

# If still failing, restart
docker compose restart qdrant
sleep 10
```

#### ❌ Weaviate: "Connection refused localhost:8080"

```bash
# Check health
curl -s http://localhost:8080/v1/.well-known/ready
# Expected: {"status": "ok"}

# Check logs for errors
docker compose logs weaviate
# Look for "grpc server listening"

# Common fix: increase wait time
sleep 20  # Weaviate needs longer startup
```

#### ❌ Milvus: "Exit 134" or "Segmentation fault"

**Problem**: Milvus unstable on macOS, especially M1/M2

**Solutions**:

1. **Increase resources**:

```bash
# In Docker Desktop: Settings > Resources
# RAM: 6GB minimum
# CPU: 4 cores minimum
```

2. **Use Rosetta (for M1/M2)**:

```bash
# In docker-compose.yml, add to milvus service:
platform: linux/amd64
```

3. **Skip Milvus**:

```bash
# Focus on Qdrant + Weaviate only
# Milvus optional for macOS users
```

### 📊 Data & Results Issues

#### ❌ "Synthetic dataset generation failed"

```bash
# Check available space
df -h ./datasets
# Need at least 2GB free

# Remove corrupted data
rm -rf datasets/cohere-mini-200k-d768/

# Manual generation
docker compose exec bench python3 -c "
from datasets import generate_synthetic_dataset
generate_synthetic_dataset('cohere-mini-200k-d768', 50000, 768, 1000)
"
```

#### ❌ "No results.json output"

**Problem**: Benchmark crashed or no output redirection

**Solutions**:

1. **Check for errors**:

```bash
# Run without output redirection first
docker compose exec bench python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768

# Look for error messages before redirecting to file
```

2. **Alternative output methods**:

```bash
# Save inside container, then copy
docker compose exec bench python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768 > /tmp/results.json
docker compose cp bench:/tmp/results.json ./results_qdrant.json
```

### 🔧 Configuration Issues

#### ❌ "Config file not found"

```bash
# Verify config exists
ls -la bench/config.yaml
# Should exist and be readable

# Check container mount
docker compose exec bench ls -la /app/bench/config.yaml
# Should be accessible inside container
```

#### ❌ "Invalid recall values" atau "Tuning failed"

```bash
# Check config.yaml target_recall_at_k
target_recall_at_k: 0.9  # Should be 0.9, not 0.99

# Verify parameter ranges in config
ef_search_start: 16   # Not too low
ef_search_max: 128    # Not too high for 50k dataset
```

### 💾 Storage & Path Issues

#### ❌ "Permission denied" di NVME_ROOT

```bash
# Fix ownership
sudo chown -R $(whoami):staff "$NVME_ROOT"
chmod 755 "$NVME_ROOT"

# Verify access
touch "$NVME_ROOT/test.txt" && rm "$NVME_ROOT/test.txt"
# Should work without errors
```

#### ❌ "No space left on device"

```bash
# Clean Docker
docker system prune -a
docker volume prune

# Check dataset size
du -sh datasets/
# Typical: 1.4GB for 50k vectors

# Clean old results
rm -f results_*.json sensitivity_*.json
```

### 🌐 Network & Environment Issues

#### ❌ "Port already in use"

```bash
# Find processes using ports
lsof -i :6333  # Qdrant
lsof -i :8080  # Weaviate
lsof -i :19530 # Milvus

# Kill if needed
sudo kill -9 <PID>

# Or use different ports in docker-compose.yml
```

#### ❌ "COHERE_API_KEY not found" (if using PDF)

```bash
# Set API key for PDF embedding
export COHERE_API_KEY="your-api-key-here"

# Verify
echo $COHERE_API_KEY

# Or use synthetic dataset instead
# Leave pdf_dir empty in config.yaml
```

### 🔍 Debug Commands

#### Quick Health Check

```bash
# System check
echo "=== System Info ==="
docker --version
docker compose --version
echo "NVME_ROOT: $NVME_ROOT"
df -h "$NVME_ROOT"

# Container check
echo "=== Container Status ==="
docker compose ps

# Database check
echo "=== Database Health ==="
curl -s http://localhost:6333/healthz || echo "Qdrant not available"
curl -s http://localhost:8080/v1/.well-known/ready || echo "Weaviate not available"
curl -s http://localhost:9091/healthz || echo "Milvus not available"
```

#### Log Analysis

```bash
# Recent errors only
docker compose logs --tail 50 qdrant | grep -i error
docker compose logs --tail 50 weaviate | grep -i error
docker compose logs --tail 50 milvus | grep -i error

# Benchmark container logs
docker compose logs bench
```

#### Resource Monitoring

```bash
# While benchmark running
docker stats

# Expected during active benchmark:
# CPU: 50-80%
# MEM: 2-4GB
# No swap usage
```

### 🚨 Emergency Recovery

#### Complete Reset

```bash
# 1. Stop everything
docker compose down

# 2. Clean Docker
docker system prune -a -f
docker volume prune -f

# 3. Clean data (DANGER: deletes all benchmark data)
# rm -rf "$NVME_ROOT"/*
# rm -rf datasets/

# 4. Rebuild from scratch
docker compose build bench
docker compose --profile bench --profile qdrant up -d
```

#### Minimal Working Test

```bash
# Simplest possible test to verify setup
docker compose --profile bench --profile qdrant up -d qdrant bench
sleep 10

# Very short test
docker compose exec bench python3 -c "
import time
print('Testing basic functionality...')
time.sleep(2)
print('✅ Container accessible')
"

# If this fails, fundamental setup issue exists
```

---

## 🧹 Cleanup & Data Management

### 🔄 Regular Cleanup (RECOMMENDED)

```bash
# Stop all containers
docker compose down

# Clean unused Docker resources
docker system prune -a
docker volume prune

# Check space usage
du -sh "$NVME_ROOT"
du -sh datasets/
du -sh results/
```

### 🗂️ Data Persistence Management

**Data Locations**:

- **Vector DB Data**: `$NVME_ROOT/*` (persistent antar sesi)
- **Datasets**: `./datasets/` (reusable)
- **Results**: `results_*.json`, `sensitivity_*.json` (backup manual)

**⚠️ IMPORTANT**: Data VDB disimpan di NVME_ROOT internal, sehingga persistent antar sesi

### 🧹 Full Reset (DANGER ZONE)

```bash
# ⚠️ WARNING: This deletes ALL benchmark data!

# 1. Stop everything
docker compose down

# 2. Clean all Docker data
docker system prune -a -f
docker volume prune -f

# 3. Clean benchmark data (IRREVERSIBLE!)
rm -rf "$NVME_ROOT"/*
rm -rf datasets/
rm -f results_*.json sensitivity_*.json

# 4. Reset environment
unset NVME_ROOT
echo 'export NVME_ROOT="/Users/$(whoami)/nvme-vdb"' >> ~/.zshrc
source ~/.zshrc
mkdir -p "$NVME_ROOT"
```

---

## 📚 Additional Resources & References

### 📖 Metodologi Paper Rujukan

Tutorial ini mengikuti **100% metodologi** paper rujukan dengan adaptasi laptop:

- ✅ **Single-machine**: Docker containers di satu laptop
- ✅ **NVMe internal**: Setup di SSD internal macOS
- ✅ **Docker containers**: Milvus, Qdrant, Weaviate isolasi
- ✅ **30s per run**: Konsisten dengan paper (dikurangi untuk testing)
- ✅ **1000 queries**: Jumlah query per benchmark run
- ✅ **5 repeats**: Rata-rata hasil untuk stabilitas
- ✅ **recall@10 ≥ 0.9**: Target accuracy minimum
- ✅ **Sensitivity study**: Parameter vs performance analysis
- ✅ **Hybrid search**: Dense + sparse (Weaviate full)
- ✅ **Analisis kuantitatif**: QPS, latency, I/O metrics

### 🔗 Useful Commands Reference

```bash
# Quick status check
docker compose ps && echo "NVME_ROOT: $NVME_ROOT" && df -h "$NVME_ROOT"

# Container logs (last 20 lines)
docker compose logs --tail 20 qdrant weaviate milvus bench

# Resource monitoring
docker stats --no-stream

# Database health check
curl -s http://localhost:6333/healthz && echo " ✅ Qdrant"
curl -s http://localhost:8080/v1/.well-known/ready && echo " ✅ Weaviate"
curl -s http://localhost:9091/healthz && echo " ✅ Milvus"

# Quick benchmark test (Qdrant only)
docker compose --profile bench --profile qdrant up -d qdrant bench && \
sleep 10 && \
docker compose exec bench python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768
```

### 📁 Project Structure Reference

```
fp-sdi/
├── docker-compose.yml          # Multi-VDB Docker setup
├── Makefile                    # Convenience commands
├── TUTORIAL.md                 # This comprehensive guide
├── bench/
│   ├── bench.py               # Main benchmark script
│   ├── config.yaml            # Configuration file
│   ├── datasets.py            # Dataset generation
│   ├── *_client.py           # VDB clients (Qdrant, Weaviate, Milvus)
│   ├── analyze_results.py     # Result analysis & plotting
│   └── requirements.txt       # Python dependencies
├── datasets/
│   └── cohere-mini-200k-d768/ # Generated synthetic dataset (1.4GB)
└── $NVME_ROOT/                # Vector database storage (persistent)
    ├── qdrant/
    ├── weaviate/
    └── milvus/
```

### 🎯 Success Metrics Summary

**Benchmark berhasil jika**:

- ✅ Dataset 1.4GB generated di `./datasets/`
- ✅ QPS > 20 untuk concurrency=1
- ✅ QPS meningkat dengan concurrency (scaling)
- ✅ P99 latency < 1000ms (ideal < 500ms)
- ✅ No container crashes atau timeouts
- ✅ Results JSON files generated dengan complete data

**Typical Laptop Results**:

- **Qdrant**: 25-35 QPS (conc=1), 70-90 QPS (conc=2)
- **Weaviate**: 20-30 QPS (conc=1), 50-70 QPS (conc=2)
- **Milvus**: 30-40 QPS (conc=1), 80-100 QPS (conc=2)

---

## 🙋‍♂️ FAQ (Frequently Asked Questions)

**Q: Apakah tutorial ini mengikuti paper rujukan?**
A: Ya, 100%. Tutorial mengikuti metodologi paper dengan adaptasi untuk laptop (50k vectors vs 200k+, tapi proporsi dan parameter sama).

**Q: Berapa lama total waktu eksperimen?**
A: ~2-3 jam untuk setup pertama + benchmark lengkap (3 VDB x 2 index). Setelah setup, ~30-45 menit per VDB.

**Q: Apakah data persistent antar sesi?**
A: Ya. Dataset di `./datasets/` dan VDB data di `$NVME_ROOT` persistent. Results manual backup ke file JSON.

**Q: VDB mana yang paling stabil di macOS?**
A: Urutan stabilitas: Qdrant > Weaviate > Milvus. Milvus sering crash di M1/M2 macOS.

**Q: Bisakah run semua VDB bersamaan?**
A: TIDAK direkomendasikan. Resource contention membuat hasil tidak valid. Jalankan sequential (satu per satu).

**Q: Minimum specs untuk laptop?**
A: RAM 8GB, CPU 4+ cores, 10GB free storage. SSD internal (bukan eksternal) untuk I/O optimal.

**Q: Bagaimana jika gagal terus?**
A: Follow troubleshooting guide. Fokus ke Qdrant dulu (paling stabil). Jika masih gagal, complete reset.

**Tutorial ini dibuat untuk memastikan eksperimen berhasil 100% dengan risiko minimal. IKUTI STEP-BY-STEP dan jangan skip verifikasi!**
