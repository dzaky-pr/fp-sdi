# bench/qdrant_helper.py
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
import numpy as np

def connect():
    return QdrantClient(url="http://qdrant:6333", grpc_port=6334, prefer_grpc=True, timeout=60.0)

def drop_recreate(client, name, dim, metric, on_disk=True):
    if client.collection_exists(name): client.delete_collection(name)
    dist = qm.Distance.COSINE if metric.lower()=="cosine" else qm.Distance.DOT
    client.recreate_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=dim, distance=dist, on_disk=on_disk),
        hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=200),
        optimizers_config=qm.OptimizersConfigDiff(memmap_threshold=20000) if on_disk else None,
    )

def insert(client, name, vectors, batch=1000, payload=None):
    ids = np.arange(len(vectors)).tolist()
    points = []
    for i, vec in enumerate(vectors):
        point = qm.PointStruct(id=ids[i], vector=vec.tolist())
        if payload and i < len(payload):
            point.payload = payload[i]
        points.append(point)
    client.upload_points(name, points, batch_size=batch, parallel=1, max_retries=3)

def search(client, name, queries, topk, ef_search=64):
    res=[]
    for q in queries:
        hits = client.search(
            name, query_vector=q.tolist(), limit=int(topk),
            params=qm.SearchParams(hnsw_ef=int(ef_search))
        )
        res.append([int(h.id) for h in hits])
    return np.array(res, dtype=int)
