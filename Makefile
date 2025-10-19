# Makefile
# Benchmark Vector Databases: Qdrant vs Weaviate
# Mengikuti metodologi paper rujukan dengan fokus HNSW-based comparison

.PHONY: help build up down clean bench-shell test-qdrant test-weaviate test-all

# Default target - show help
help:
	@echo "======================================================================="
	@echo "Vector Database Benchmark - Qdrant vs Weaviate"
	@echo "======================================================================="
	@echo ""
	@echo "Available targets:"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start Qdrant, Weaviate, dan Bench containers"
	@echo "  make down          - Stop all containers"
	@echo "  make clean         - Stop containers and remove volumes"
	@echo "  make bench-shell   - Open shell di bench container"
	@echo "  make test-qdrant   - Run quick test untuk Qdrant"
	@echo "  make test-weaviate - Run quick test untuk Weaviate"
	@echo "  make test-all      - Run tests untuk semua databases"
	@echo ""
	@echo "Benchmark commands (run dari bench-shell):"
	@echo "  python3 bench.py --db qdrant --index hnsw --dataset cohere-mini-200k-d768"
	@echo "  python3 bench.py --db weaviate --index hnsw --dataset cohere-mini-200k-d768"
	@echo ""

build:
	@echo "Building Docker images..."
	docker compose build

up:
	@echo "Starting Qdrant, Weaviate, and Bench containers..."
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@docker compose ps
	@echo ""
	@echo "✅ Services are up! Run 'make bench-shell' to start benchmarking."

down:
	@echo "Stopping all containers..."
	docker compose down

clean:
	@echo "Stopping containers and removing volumes..."
	docker compose down -v
	@echo "Cleaning up data directories..."
	rm -rf ./nvme/qdrant/* ./nvme/weaviate/*
	@echo "✅ Cleanup complete!"

bench-shell:
	@echo "Opening shell in bench container..."
	docker compose exec bench bash

test-qdrant:
	@echo "Testing Qdrant connection..."
	docker compose exec bench python3 -c "from qdrant_helper import test_connection; test_connection()"

test-weaviate:
	@echo "Testing Weaviate connection..."
	docker compose exec bench python3 -c "from weaviate_client import test_connection; test_connection()"

test-all: test-qdrant test-weaviate
	@echo "✅ All connection tests passed!"

