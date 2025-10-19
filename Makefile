# Makefile
.PHONY: build up-milvus up-qdrant up-weaviate bench-shell down

build:
	docker compose build

up-milvus:
	docker compose --profile milvus --profile bench up -d milvus bench

up-qdrant:
	docker compose --profile qdrant --profile bench up -d qdrant bench

up-weaviate:
	docker compose --profile weaviate --profile bench up -d weaviate bench

bench-shell:
	docker compose exec bench bash

down:
	docker compose down -v
