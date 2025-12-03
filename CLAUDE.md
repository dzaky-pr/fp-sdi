# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **vector database benchmark project** comparing Qdrant vs Weaviate for semantic search. The project follows academic research methodology with a focus on HNSW (Hierarchical Navigable Small World) index comparison on commodity hardware (MacBook Pro with 8GB RAM).

**Key characteristics:**
- Research-oriented benchmark (not production application)
- Sequential execution model (one database at a time for fairness)
- Docker-based deployment with NVMe storage
- Focus on apple-to-apple HNSW comparison
- Synthetic dataset generation for reproducibility

## Architecture

### Core Components

The codebase is organized into 5 Python modules in the [bench/](bench/) directory:

1. **[bench.py](bench/bench.py)** - Main orchestrator
   - Entry point for all benchmarks
   - Manages concurrency grid (configured in [config.yaml](bench/config.yaml), default: [1, 2])
   - Budget-based execution (prevents runaway tests, default: 300s)
   - Supports modes: standard and sensitivity study (`--sensitivity`)
   - **Latency tracking**: Records per-query latency (min, mean, P50, P95, P99, max)
   - **Sensitivity study mode**: Tests multiple ef values (64, 128, 192, 256) for recall vs performance tradeoff

2. **[clients.py](bench/clients.py)** - Database abstraction layer
   - `QdrantClientHelper`: Qdrant client wrapper (gRPC preferred on port 6334, HTTP on 6333, timeout: 60s)
   - `WeaviateClient`: Weaviate client wrapper (HTTP on port 8080)
   - Standardized interface: `connect()`, `drop_recreate()`, `insert()`, `search()`
   - **Qdrant-specific**: On-disk mode (`on_disk=True`), per-query ef_search
   - **Weaviate-specific**: ef as class-level config during `drop_recreate()`

3. **[datasets.py](bench/datasets.py)** - Dataset management
   - Generates synthetic vectors using numpy random normal distribution
   - Supports 3 datasets: msmarco-mini-10k-d384, cohere-mini-50k-d768, openai-ada-10k-d1536
   - Caches embeddings to `.npy` files in `/datasets` for efficiency
   - Lightweight and fast (no external embedding models required)

4. **[monitoring.py](bench/monitoring.py)** - System metrics collection
   - **CPU tracking**: Docker stats API (preferred) with psutil fallback, samples every 0.2s
   - **I/O monitoring**: 3-tier fallback strategy (bpftrace → iostat → psutil)
   - **macOS compatibility**: Auto-detects platform (Darwin/Linux) and uses appropriate iostat format

5. **[utils.py](bench/utils.py)** - Helper utilities
   - Percentile calculations (P50, P95, P99) using linear interpolation
   - Brute-force top-k search for ground truth (supports IP, COSINE, L2 metrics)
   - Recall@k calculation via set intersection
   - Lightweight module with minimal dependencies (numpy only)

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
- **Qdrant**: `${NVME_ROOT}/qdrant:/qdrant/storage`
- **Weaviate**: `${NVME_ROOT}/weaviate:/var/lib/weaviate`
- **Bench**: `./bench:/app`, `./datasets:/datasets`, `./results:/results`

**Required environment variable:**
```bash
export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
```

**Docker images used:**
- **Qdrant**: `qdrant/qdrant:v1.14.1` (ports: 6333 HTTP, 6334 gRPC)
- **Weaviate**: `semitechnologies/weaviate:1.31.0` (port: 8080)
- **Bench**: Custom build from `bench/Dockerfile` (Python 3.13-slim with bpftrace, fio, iotop, sysstat, linux-perf)

**Healthchecks**:
- Qdrant: `curl http://localhost:6333/healthz` (interval: 10s, retries: 30)
- Weaviate: `wget http://localhost:8080/v1/meta` (interval: 10s, retries: 30)

### Configuration File (config.yaml)

The [config.yaml](bench/config.yaml) file centralizes all benchmark parameters:

```yaml
# Runtime configuration
concurrency_grid: [1, 2]           # Concurrency levels to test
repeats: 5                          # Repetitions per concurrency level
run_seconds: 10                     # Duration per test run
topk: 10                            # Number of nearest neighbors
seed: 42                            # Reproducibility seed
data_root: /datasets                # Dataset storage path
gt_queries_for_recall: 128          # Ground truth queries for recall calculation

# Datasets
datasets:
  - name: msmarco-mini-10k-d384
    dim: 384
    n_vectors: 10000
    n_queries: 1000
  - name: cohere-mini-50k-d768
    dim: 768
    n_vectors: 50000
    n_queries: 1000
  - name: openai-ada-10k-d1536
    dim: 1536
    n_vectors: 10000
    n_queries: 1000

# HNSW index parameters (per database)
indexes:
  qdrant:
    hnsw:
      build:
        ef_construct: 200
        m: 16
      metric: Cosine
      on_disk: true
  weaviate:
    hnsw:
      build:
        efConstruction: 200
        maxConnections: 16
      metric: cosine
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
python3 bench.py --db qdrant --dataset msmarco-mini-10k-d384
python3 bench.py --db qdrant --dataset cohere-mini-50k-d768
python3 bench.py --db qdrant --dataset openai-ada-10k-d1536

# ===========================================
# WEAVIATE BENCHMARK (Stop Qdrant first)
# ===========================================
# From host:
docker compose stop qdrant && docker compose start weaviate

# In bench-shell:
python3 bench.py --db weaviate --dataset msmarco-mini-10k-d384
python3 bench.py --db weaviate --dataset cohere-mini-50k-d768
python3 bench.py --db weaviate --dataset openai-ada-10k-d1536
```

**Sensitivity study** (parameter tuning across ef values):
```bash
# Tests ef ∈ {64, 128, 192, 256} to analyze recall vs performance tradeoff
python3 bench.py --db qdrant --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600

# Note: Weaviate recreates the collection for each ef value (slower)
# Qdrant can change ef_search per query (faster)
python3 bench.py --db weaviate --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600
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

**Common issues and solutions:**

1. **`NVME_ROOT` not set error when running `make up`:**
   ```bash
   export NVME_ROOT="/Users/dzakyrifai/nvme-vdb"
   mkdir -p "$NVME_ROOT"
   make up
   ```

2. **Healthcheck failures:**
   ```bash
   # Check service status
   docker compose ps

   # View logs for errors
   docker compose logs qdrant
   docker compose logs weaviate

   # Restart unhealthy services
   docker compose restart qdrant weaviate
   ```

3. **Connection refused errors:**
   ```bash
   # Test connectivity
   curl http://localhost:6333/healthz    # Qdrant
   curl http://localhost:8080/v1/meta    # Weaviate

   # Ensure services are running
   docker compose ps
   make test-all
   ```

4. **Low recall values (~10% instead of expected ~90%):**
   - Expected with synthetic random data (default datasets)
   - Use `--sensitivity` to test higher ef values
   - Synthetic data provides consistent performance benchmarks

5. **I/O monitoring shows zeros:**
   - bpftrace likely unavailable in container (expected on macOS)
   - Fallback to iostat is automatic
   - Normal behavior for macOS host

6. **Inconsistent performance results:**
   ```bash
   # Ensure only ONE database is running
   docker compose stop weaviate  # When testing Qdrant
   docker compose stop qdrant    # When testing Weaviate

   # Check resource usage
   docker stats

   # Check disk space
   df -h "$NVME_ROOT"
   du -sh "$NVME_ROOT"
   ```

## Research Context

### Implementation Details

**Concurrency model:**
- Uses Python's `ThreadPoolExecutor` with configurable worker count
- Each worker processes a chunk of queries in a tight loop for `run_seconds`
- Threads stop simultaneously when time budget expires
- Per-query latency tracked individually across all threads

**Ground truth calculation:**
- Uses brute-force exhaustive search for exact top-k results
- Limited to first 64 queries (for performance, configurable via `gt_queries_for_recall`)
- Recall calculated as: `len(intersection(ground_truth, results)) / (k × num_queries)`

**Sensitivity study behavior:**
- **Qdrant**: Tests 4 ef_search values on the same collection (efficient)
- **Weaviate**: Recreates collection for each ef value (time-consuming, but required by API design)
- Each ef value gets full concurrency_grid × repeats treatment
- Results include `"ef": <value>` field for analysis

**Monitoring fallback chain:**
- **CPU**: docker.stats() → psutil.cpu_percent() → 0.0
- **I/O**: bpftrace (block layer) → iostat (disk stats) → psutil.disk_io_counters() → zeros
- macOS-specific: iostat format differs from Linux (handled automatically)

### Datasets

Three datasets represent different dimensional complexities:

| Dataset | Dimensions | Vectors | Purpose |
|---------|-----------|---------|---------|
| msmarco-mini-10k-d384 | 384D | 10k | Baseline (low-dim) |
| cohere-mini-50k-d768 | 768D | 50k | Main test (medium-dim) |
| openai-ada-10k-d1536 | 1536D | 10k | Stress test (high-dim) |

All datasets use **synthetic random vectors** generated with numpy for:
- Reproducibility (fixed seed)
- Fast generation (no external API calls)
- Consistent benchmarking across runs
- No external dependencies on embedding models

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

### Latency Metrics

All benchmarks track comprehensive latency metrics for each concurrency/repeat run:
- `min_latency_ms`: Minimum query latency
- `mean_latency_ms`: Average query latency
- `p50_latency_ms`: Median latency (50th percentile)
- `p95_latency_ms`: 95th percentile latency
- `p99_latency_ms`: 99th percentile latency
- `max_latency_ms`: Maximum query latency

These are calculated from per-query latency arrays collected during the benchmark run.

## Code Modification Guidelines

### Adding New Vector Databases

1. Create client class in [clients.py](bench/clients.py) with standard interface
2. Add database to [docker-compose.yml](docker-compose.yml)
3. Update [bench.py](bench/bench.py) argument parser
4. Test with `make test-all`

### Adding New Datasets

1. Define dataset in [config.yaml](bench/config.yaml)
2. Datasets are auto-generated as synthetic random vectors
3. Update dataset list in benchmark commands

### Modifying Benchmark Parameters

Key parameters are configured in [config.yaml](bench/config.yaml):

**Runtime parameters:**
- `concurrency_grid`: Worker counts (default: [1, 2])
- `run_seconds`: Duration per concurrency test (default: 10s)
- `repeats`: Statistical reliability (default: 5× per concurrency level)
- `topk`: Number of nearest neighbors to retrieve (default: 10)
- `seed`: Random seed for reproducibility (default: 42)
- `gt_queries_for_recall`: Number of queries for recall calculation (default: 128, limited to 64 in code)

**Command-line overrides:**
- `--budget_s`: Total wall-clock time limit (default: 300s)
- `--sensitivity`: Run sensitivity study across multiple ef values

**HNSW build parameters** (configured in [config.yaml](bench/config.yaml)):
- **Qdrant**: `ef_construct=200`, `m=16`, `on_disk=true`, `metric=Cosine`
- **Weaviate**: `efConstruction=200`, `maxConnections=16`, `metric=cosine`

**HNSW search parameters** (sensitivity study tests these):
- **Qdrant**: `ef_search` ∈ {64, 128, 192, 256}
- **Weaviate**: `ef` ∈ {64, 128, 192, 256}

## Result Files

Benchmarks automatically save to `results/` with naming convention:
```
results/<db>_<dataset>.json                      # Standard run
results/<db>_<dataset>_sensitivity.json          # Sensitivity study (--sensitivity)
```

**JSON structure** (per-run entry):
```json
{
  "conc": 1,                        // Concurrency level
  "qps": 200.0,                      // Queries per second
  "cpu": 795.33,                     // CPU usage percentage
  "avg_bandwidth_mb_s": 0.106,       // I/O bandwidth (MB/s)
  "read_mb": 0.454,                  // Total read (MB)
  "write_mb": 0.610,                 // Total write (MB)
  "elapsed": 19.175,                 // Actual wall-clock time (seconds)
  "min_latency_ms": 8779.31,         // Minimum latency
  "mean_latency_ms": 9586.14,        // Mean latency
  "p50_latency_ms": 9586.14,         // Median latency
  "p95_latency_ms": 10312.29,        // 95th percentile
  "p99_latency_ms": 10376.84,        // 99th percentile
  "max_latency_ms": 10392.97,        // Maximum latency
  "recall": 0.1016,                  // Recall@10 accuracy
  "ef": 64                            // (Sensitivity mode only) ef parameter tested
}
```

**Note**: Standard runs contain multiple entries (concurrency_grid × repeats). Sensitivity runs add `ef` field and test 4 ef values.

## Dependencies

The project uses minimal dependencies (from [requirements.txt](bench/requirements.txt)):

**Core libraries:**
- `numpy>=1.26` - Numerical operations and vector storage
- `pandas>=2.2` - Data analysis
- `PyYAML>=6.0.1` - Configuration parsing

**Vector database clients:**
- `qdrant-client==1.9.1` - Qdrant Python client
- `weaviate-client==3.25.3` - Weaviate Python client

**Monitoring and system tools:**
- `psutil>=5.9` - System resource monitoring
- `docker>=7.0` - Docker API for container stats
- `requests>=2.32` - HTTP requests

**Utilities:**
- `tqdm>=4.66` - Progress bars
- `matplotlib>=3.5` - Plotting (for analyze_results.py)

**System tools** (installed in Docker container):
- `bpftrace` - Advanced I/O tracing
- `fio` - Flexible I/O tester
- `iotop` - I/O monitoring
- `sysstat` (iostat) - System statistics
- `linux-perf` - Performance analysis

## Command Reference

**Supported commands:**
```bash
# Standard benchmark
python3 bench.py --db qdrant --dataset msmarco-mini-10k-d384
python3 bench.py --db qdrant --dataset cohere-mini-50k-d768
python3 bench.py --db qdrant --dataset openai-ada-10k-d1536

python3 bench.py --db weaviate --dataset msmarco-mini-10k-d384
python3 bench.py --db weaviate --dataset cohere-mini-50k-d768
python3 bench.py --db weaviate --dataset openai-ada-10k-d1536

# Sensitivity study (tests ef ∈ {64, 128, 192, 256})
python3 bench.py --db qdrant --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600
python3 bench.py --db weaviate --dataset cohere-mini-50k-d768 --sensitivity --budget_s 600
```

**Required flags:**
- `--db`: Database backend (qdrant or weaviate)
- `--dataset`: Dataset name from config.yaml

**Optional flags:**
- `--budget_s`: Wall-clock time limit in seconds (default: 300)
- `--sensitivity`: Run sensitivity study across multiple ef values

## References

- Main README: [README.md](README.md)
- Qdrant docs: https://qdrant.tech/documentation/
- Weaviate docs: https://weaviate.io/developers/weaviate
- HNSW algorithm: https://arxiv.org/abs/1603.09320
