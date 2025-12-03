# /bench/clients.py

import numpy as np
import weaviate
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


class WeaviateClient:
    def connect(self):
        # Default single-node HTTP endpoint from docker-compose
        return weaviate.Client("http://weaviate:8080")

    def drop_recreate(self, client, classname, dim, metric, ef=None):
        # Delete class if exists
        try:
            if client.schema.exists(classname):
                client.schema.delete_class(classname)
        except Exception:
            # Fallback for older versions without exists()
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
            ],
        }
        client.schema.create_class(cls)

    def insert(self, client, classname, vectors, batch=2000):
        """Insert vectors into Weaviate."""
        N = len(vectors)
        with client.batch(batch_size=batch) as b:
            for i in range(N):
                v = vectors[i]
                obj = {"pid": int(i)}
                b.add_data_object(obj, class_name=classname, vector=v.tolist())

    def search(self, client, classname, queries, topk, ef=64):
        """Return array shape (nq, topk) with pid results."""
        res = []
        for i, q in enumerate(queries):
            qb = client.query.get(classname, ["pid"])
            qb = qb.with_near_vector({"vector": q.tolist(), "certainty": 0.0})
            r = qb.with_limit(int(topk)).do()
            objs = r.get("data", {}).get("Get", {}).get(classname, []) or []
            res.append([int(o["pid"]) for o in objs])
        return np.array(res, dtype=int)


class QdrantClientHelper:
    def connect(self):
        # prefer_grpc for better throughput
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

    def insert(self, client, name, vectors, batch=1000):
        """Insert vectors into Qdrant."""
        ids = np.arange(len(vectors)).tolist()
        points = []
        for i, vec in enumerate(vectors):
            p = qm.PointStruct(id=ids[i], vector=vec.tolist())
            points.append(p)
        client.upsert(collection_name=name, points=points, wait=True)

    def search(self, client, name, queries, topk, ef_search=64):
        """Return array shape (nq, topk) with id results."""
        out = []
        for q in queries:
            hits = client.search(
                name,
                query_vector=q.tolist(),
                limit=int(topk),
                search_params=qm.SearchParams(hnsw_ef=int(ef_search)),
            )
            out.append([int(h.id) for h in hits])
        return np.array(out, dtype=int)
