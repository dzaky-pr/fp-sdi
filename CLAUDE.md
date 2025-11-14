# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **vector database benchmark project** comparing Qdrant vs Weaviate for semantic search on PDF documents. The project follows academic research methodology with a focus on HNSW (Hierarchical Navigable Small World) index comparison on commodity hardware (MacBook Pro with 8GB RAM).

**Key characteristics:**
- Research-oriented benchmark (not production application)
- Sequential execution model (one database at a time for fairness)
- Docker-based deployment with NVMe storage
- Focus on apple-to-apple HNSW comparison (Milvus excluded due to resource constraints)

## Architecture

### Core Components

The codebase is organized into 6 Python modules in the [bench/](bench/) directory:

1. **[bench.py](bench/bench.py)** - Main orchestrator
   - Entry point for all benchmarks
   - Manages concurrency grid (1-2 workers)
   - Handles HNSW parameter tuning (ef_search/ef)
   - Budget-based execution (prevents runaway tests)
   - Supports modes: standard, quick (`--quick5`), sensitivity study, baseline I/O

2. **[clients.py](bench/clients.py)** - Database abstraction layer
   - `QdrantClientHelper`: Qdrant client wrapper (gRPC/HTTP)
   - `WeaviateClient`: Weaviate client wrapper
   - Standardized interface: `connect()`, `drop_recreate()`, `insert()`, `search()`
   - Easy extensibility for new vector databases

3. **[datasets.py](bench/datasets.py)** - Dataset management
   - Generates synthetic vectors or loads from SentenceTransformers
   - Supports 3 datasets: msmarco-mini-10k-d384, cohere-mini-50k-d768, openai-ada-10k-d1536
   - Caches embeddings to `.npy` files for efficiency
   - Hybrid search support with BM25 sparse vectors

4. **[monitoring.py](bench/monitoring.py)** - System metrics collection
   - CPU usage tracking via Docker stats
   - I/O monitoring (bpftrace with iostat fallback)
   - Page cache flushing for consistent I/O measurements
   - FIO baseline test for disk performance

5. **[utils.py](bench/utils.py)** - Helper utilities
   - Percentile calculations (P50, P95, P99 latency)
   - Brute-force top-k search for ground truth
   - Recall@10 calculation
   - Page cache flush implementation

6. **[analyze_results.py](bench/analyze_results.py)** - Results analysis
   - Parses JSON benchmark results
   - Generates plots (QPS, latency, CPU, I/O)
   - Bottleneck analysis (CPU-bound vs I/O-bound detection)
   - Summary statistics with cross-database comparison

### Service Architecture (Docker Compose)

```
┌─────────────┐
│    bench    │ ← Run benchmarks here (Python container)
│  container  │
└──────┬──────┘
       │
       ├─────→ qdrant:6333    (Qdrant vector DB)
       └─────→ weaviate:8080  (Weaviate vector DB)
```

**CRITICAL:** Only ONE database runs during benchmarks for fairness (sequential execution model). Use `docker compose stop <db>` to switch.

### Volume Mapping (NVMe Storage)

All databases store data on NVMe for consistent I/O performance:
- Qdrant: `${NVME_ROOT}/qdrant:/qdrant/storage`
- Weaviate: `${NVME_ROOT}/weaviate:/var/lib/weaviate`
- FIO: `${NVME_ROOT}/fio:/target`

**Required environment variable:**
```bash
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
```

## Common Development Commands

### Initial Setup

```bash
# 1. Setup NVMe path (REQUIRED - must be set before starting services)
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
mkdir -p "$NVME_ROOT"

# Verify (MUST output: /Users/dzakyrifai/nvme-vdb)
echo "$NVME_ROOT"

# 2. Build and start services
make build
make up

# 3. Verify connectivity
make test-all
```

### Running Benchmarks

**IMPORTANT:** Always run benchmarks **sequentially** (one database at a time):

```bash
# Enter benchmark container
make bench-shell

# ===========================================
# QDRANT BENCHMARK (Stop Weaviate first)
# ===========================================
# From host terminal:
docker compose stop weaviate

# In bench-shell:
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768

# ===========================================
# WEAVIATE BENCHMARK (Stop Qdrant first)
# ===========================================
# From host:
docker compose stop qdrant && docker compose start weaviate

# In bench-shell:
python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-50k-d768
```

**Quick mode** (≤5 minutes, for testing):
```bash
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --quick5
```

**Sensitivity study** (parameter tuning):
```bash
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600
```

**Memory-limited mode** (for 8GB RAM):
```bash
python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-50k-d768 --limit_n 5000
```

### Analysis

```bash
# Exit bench container first
exit

# Analyze results (from host)
python3 bench/analyze_results.py --results results/qdrant_cohere-mini-50k-d768.json results/weaviate_cohere-mini-50k-d768.json
```

### Database Management

```bash
# Switch databases (sequential execution)
docker compose stop weaviate              # Use Qdrant only
docker compose stop qdrant                # Use Weaviate only
docker compose start qdrant weaviate      # Start all

# Restart services
make down && make up

# Clean volumes (removes all data)
make clean
```

### Troubleshooting

```bash
# Check service status
docker compose ps

# View logs
docker compose logs qdrant
docker compose logs weaviate

# Check resource usage
docker stats

# Test connectivity
curl http://localhost:6333/healthz    # Qdrant
curl http://localhost:8080/v1/meta    # Weaviate

# Check disk space
df -h "$NVME_ROOT"
du -sh "$NVME_ROOT"
```

## Research Context

### The 4 Research Questions

This project answers 4 specific research questions documented in [laporan_eksperimen/](laporan_eksperimen/):

1. **Model Kueri** ([nomor_1](laporan_eksperimen/nomor_1_model_kueri/)): Pure vector (Qdrant) vs hybrid search (Weaviate)
2. **Parameter HNSW** ([nomor_2](laporan_eksperimen/nomor_2_parameter_hnsw/)): ef parameter sensitivity analysis
3. **Skalabilitas** ([nomor_3](laporan_eksperimen/nomor_3_skala_konkurensi/)): Concurrency and dimensional scaling
4. **Sensitivitas Dimensi** ([nomor_4](laporan_eksperimen/nomor_4_sensitivitas_dimensi/)): 384D, 768D, 1536D comparison

### Key Research Findings (Completed)

- **Qdrant**: 3.7× faster QPS, 4.3× faster P99 latency, higher out-of-box recall
- **Weaviate**: 40% lower CPU usage, +37% recall improvement with tuning
- **Bottleneck**: CPU-bound workloads across all dimensions (I/O not limiting)
- **Scaling anomaly**: 1536D shows negative scaling with concurrency (memory bandwidth limit)

### Datasets

Three datasets represent different dimensional complexities:

| Dataset | Dimensions | Vectors | Purpose |
|---------|-----------|---------|---------|
| msmarco-mini-10k-d384 | 384D | 10k | Baseline (low-dim) |
| cohere-mini-50k-d768 | 768D | 50k | Main test (medium-dim) |
| openai-ada-10k-d1536 | 1536D | 10k | Stress test (high-dim) |

Memory limits for 8GB RAM:
- 384D: `--limit_n 5000` (both databases)
- 768D: `--limit_n 5000` (Qdrant), `--limit_n 3000` (Weaviate)
- 1536D: `--limit_n 2000` (both databases)

## Important Constraints

### Sequential Execution Model

**CRITICAL:** Never run both databases simultaneously during benchmarks. This ensures:
- Fair resource allocation (no CPU/RAM contention)
- Accurate performance measurements
- Reproducible results
- Proper I/O attribution

### NVME_ROOT Environment Variable

The `NVME_ROOT` variable **MUST** be set before starting services:
```bash
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
```

Without it, `make up` will fail with an error. This path is hardware-specific for the MacBook Pro setup.

### Memory Management

On 8GB RAM systems, always use `--limit_n` to prevent OOM errors:
- Without limit: Process exits with code 137
- Solution: Use conservative vector counts per dataset dimension

### P99 Latency Tracking

All benchmarks now include P99 latency measurement (previously missing). Results include:
- `min_p99`: Minimum 99th percentile latency across runs
- `latencies`: Per-query latency array for percentile calculations

## Code Modification Guidelines

### Adding New Vector Databases

1. Create client class in [clients.py](bench/clients.py) with standard interface
2. Add database to [docker-compose.yml](docker-compose.yml)
3. Update [bench.py](bench/bench.py) argument parser
4. Test with `make test-all`

### Adding New Datasets

1. Define dataset in [datasets.py](bench/datasets.py)
2. Generate or load embeddings (cache to `.npy`)
3. Update dataset list in benchmark commands
4. Document memory requirements

### Modifying Benchmark Parameters

Key parameters in [bench.py](bench/bench.py):
- `concurrency_grid`: Worker counts (default: [1, 2])
- `run_seconds`: Duration per test (default: 10s)
- `repeats`: Statistical reliability (default: 5×)
- `budget_s`: Total time limit (default: 300s, sensitivity: 600s)

HNSW parameters (per database):
- **Qdrant**: `ef_construct=200`, `m=16`, `ef_search=64-256`
- **Weaviate**: `efConstruction=200`, `maxConnections=16`, `ef=64-256`

## Result Files

Benchmarks automatically save to `results/` with naming:
```
results/<db>_<dataset>_[sensitivity|quick].json
results/<db>_<dataset>/summary.json
```

JSON structure includes:
- `conc`: Concurrency level
- `qps`: Queries per second
- `cpu`: CPU usage percentage
- `min_p99`: P99 latency (ms)
- `avg_bandwidth_mb_s`: I/O bandwidth
- `recall_at_k`: Recall@10 accuracy

## Performance Baselines

Expected results on MacBook Pro 13-inch (Intel i5, 8GB RAM):

**Qdrant (cohere-mini-50k-d768):**
- QPS: 458, Recall: 0.898, P99: ~3000ms, CPU: 183%

**Weaviate (cohere-mini-50k-d768):**
- QPS: 125, Recall: 0.766, P99: ~13000ms, CPU: 112%

Deviations suggest environment issues (check Docker resources, NVME path, sequential execution).

## References

- Main README: [README.md](README.md)
- Research reports: [laporan_eksperimen/](laporan_eksperimen/)
- Qdrant docs: https://qdrant.tech/documentation/
- Weaviate docs: https://weaviate.io/developers/weaviate
