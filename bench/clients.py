# bench/clients.py
import weaviate, numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

class WeaviateClient:
    def connect(self):
        return weaviate.Client("http://weaviate:8080")

    def drop_recreate(self, client, classname, dim, metric, ef=None):
        if client.schema.exists(classname):
            client.schema.delete_class(classname)
        vic = {"distance": metric, "efConstruction": 200, "maxConnections": 16}
        if ef is not None:
            vic["ef"] = int(ef)  # jika server mendukung, akan dipakai
        cls = {
          "class": classname,
          "vectorIndexType": "hnsw",
          "vectorIndexConfig": vic,
          "properties": [{"name":"pid","dataType":["int"]}],
        }
        client.schema.create_class(cls)

    def insert(self, client, classname, vectors, batch=2000):
        with client.batch(batch_size=batch) as b:
            for i, v in enumerate(vectors):
                b.add_data_object({"pid": int(i)}, class_name=classname, vector=v.tolist())

    def search(self, client, classname, queries, topk, ef=64, hybrid=False, query_texts=None):
        res=[]
        for i, q in enumerate(queries):
            query_builder = client.query.get(classname, ["pid"])
            if hybrid and query_texts and i < len(query_texts):
                query_builder = query_builder.with_hybrid(query_texts[i], vector=q.tolist(), alpha=0.5)
            else:
                query_builder = query_builder.with_near_vector({"vector": q.tolist()})
            r = query_builder.with_limit(int(topk)).do()
            objs = r.get("data",{}).get("Get",{}).get(classname,[]) or []
            res.append([int(o["pid"]) for o in objs])
        return np.array(res, dtype=int)

class QdrantClientHelper:
    def connect(self):
        return QdrantClient(url="http://qdrant:6333", grpc_port=6334, prefer_grpc=True, timeout=60.0)

    def drop_recreate(self, client, name, dim, metric, on_disk=True):
        if client.collection_exists(name): client.delete_collection(name)
        dist = qm.Distance.COSINE if metric.lower()=="cosine" else qm.Distance.DOT
        client.recreate_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=dist, on_disk=on_disk),
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=200),
            optimizers_config=qm.OptimizersConfigDiff(memmap_threshold=20000) if on_disk else None,
        )

    def insert(self, client, name, vectors, batch=1000, payload=None):
        ids = np.arange(len(vectors)).tolist()
        points = []
        for i, vec in enumerate(vectors):
            point = qm.PointStruct(id=ids[i], vector=vec.tolist())
            if payload and i < len(payload):
                point.payload = payload[i]
            points.append(point)
        client.upload_points(name, points, batch_size=batch, parallel=1, max_retries=3)

    def search(self, client, name, queries, topk, ef_search=64):
        res=[]
        for q in queries:
            hits = client.search(
                name, query_vector=q.tolist(), limit=int(topk),
                search_params=qm.SearchParams(hnsw_ef=int(ef_search))
            )
            res.append([int(h.id) for h in hits])
        return np.array(res, dtype=int)