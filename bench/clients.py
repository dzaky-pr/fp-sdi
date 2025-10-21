# bench/clients.py

import numpy as np
import weaviate
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


class WeaviateClient:
    def connect(self):
        # Default single-node HTTP endpoint from docker-compose
        return weaviate.Client("http://weaviate:8080")

    def drop_recreate(self, client, classname, dim, metric, ef=None):
        # Hapus class jika ada
        try:
            if client.schema.exists(classname):
                client.schema.delete_class(classname)
        except Exception:
            # fallback kalau exists() tidak tersedia pada versi tertentu
            try:
                schema = client.schema.get()
                if any(c.get("class") == classname for c in schema.get("classes", [])):
                    client.schema.delete_class(classname)
            except Exception:
                pass

        vic = {"distance": metric, "efConstruction": 200, "maxConnections": 16}
        if ef is not None:
            # Set ef as the default search ef for this class
            vic["ef"] = int(ef)

        cls = {
            "class": classname,
            "vectorizer": "none",
            "vectorIndexType": "hnsw",
            "vectorIndexConfig": vic,
            "properties": [
                {"name": "pid", "dataType": ["int"]},
                # Field teks untuk hybrid BM25+vector
                {"name": "content", "dataType": ["text"]},
            ],
        }
        client.schema.create_class(cls)

    def insert(self, client, classname, vectors, texts=None, batch=2000):
        """
        Insert data:
        - vectors: np.ndarray shape (N, D)
        - texts: list[str] panjang N untuk field 'content' (opsional)
        """
        N = len(vectors)
        with client.batch(batch_size=batch) as b:
            for i in range(N):
                v = vectors[i]
                obj = {"pid": int(i)}
                if texts is not None and i < len(texts):
                    obj["content"] = texts[i]
                b.add_data_object(obj, class_name=classname, vector=v.tolist())

    def search(self, client, classname, queries, topk, ef=64, hybrid=False, query_texts=None):
        """
        Kembalikan array shape (nq, topk) berisi pid hasil teratas.
        - hybrid=True => pakai .with_hybrid(query_texts[i], vector=..., alpha=0.5)
        """
        res = []
        for i, q in enumerate(queries):
            qb = client.query.get(classname, ["pid"])
            if hybrid and query_texts and i < len(query_texts):
                qb = qb.with_hybrid(query_texts[i], vector=q.tolist(), alpha=0.5)
            else:
                # Set ef in the near_vector parameters
                qb = qb.with_near_vector({"vector": q.tolist(), "certainty": 0.0})  # certainty might not be needed
            r = qb.with_limit(int(topk)).do()
            objs = r.get("data", {}).get("Get", {}).get(classname, []) or []
            res.append([int(o["pid"]) for o in objs])
        return np.array(res, dtype=int)


class QdrantClientHelper:
    def connect(self):
        # prefer_grpc untuk throughput lebih baik, tapi HTTP tetap ada
        return QdrantClient(url="http://qdrant:6333", grpc_port=6334, prefer_grpc=True, timeout=60.0)

    def drop_recreate(self, client, name, dim, metric, on_disk=True):
        if client.collection_exists(name):
            client.delete_collection(name)

        dist = qm.Distance.COSINE if metric.lower() == "cosine" else qm.Distance.DOT
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=dist, on_disk=on_disk),
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=200),
            optimizers_config=qm.OptimizersConfigDiff(memmap_threshold=20000) if on_disk else None,
        )

    def insert(self, client, name, vectors, batch=1000, payload=None):
        ids = np.arange(len(vectors)).tolist()
        points = []
        has_payload = payload is not None and len(payload) == len(vectors)
        for i, vec in enumerate(vectors):
            p = qm.PointStruct(id=ids[i], vector=vec.tolist())
            if has_payload:
                p.payload = payload[i]
            points.append(p)
        client.upsert( collection_name=name, points=points, wait=True)


    def search(self, client, name, queries, topk, ef_search=64, filter_=None):
        """
        Kembalikan array shape (nq, topk) id hasil.
        - filter_: qm.Filter(...) untuk payload filtering (opsional)
        """
        out = []
        for q in queries:
            hits = client.search(
                name,
                query_vector=q.tolist(),
                limit=int(topk),
                search_params=qm.SearchParams(hnsw_ef=int(ef_search)),
                query_filter=filter_,
            )
            out.append([int(h.id) for h in hits])
        return np.array(out, dtype=int)
