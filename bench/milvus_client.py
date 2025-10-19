# bench/milvus_client.py
from pymilvus import MilvusClient, DataType
import math, numpy as np, time, requests

def _nlist_rule(n): 
    return max(1, int(4*math.sqrt(n)))

def connect(retries=60, wait=1.0):
    for _ in range(retries):
        try:
            if requests.get("http://milvus:9091/healthz", timeout=1).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(wait)
    last=None
    for _ in range(retries):
        try:
            c = MilvusClient(uri="http://milvus:19530")
            c.list_collections()
            return c
        except Exception as e:
            last=e; time.sleep(wait)
    raise RuntimeError(f"Milvus not ready: {last}")

def _schema(dim, metric):
    return {
        "collection_name": "bench",
        "fields": [
            {"name":"id","dtype":DataType.INT64,"is_primary":True,"auto_id":True},
            {"name":"vec","dtype":DataType.FLOAT_VECTOR,"dim":dim}
        ],
        "metric_type": metric
    }

def drop_recreate(client, dim, metric):
    if client.has_collection("bench"): client.drop_collection("bench")
    client.create_collection(_schema(dim, metric))

def insert_and_flush(client, vectors, batch=5000):
    N=len(vectors); off=0
    while off < N:
        client.insert("bench", data={"vec": vectors[off:off+batch].tolist()})
        off += batch
    client.flush("bench")

def build_index_ivf(client, n, metric, nlist):
    client.create_index("bench","vec",{"index_type":"IVF_FLAT","metric_type":metric,"params":{"nlist": int(nlist)}})

def build_index_hnsw(client, metric, M, efc):
    client.create_index("bench","vec",{"index_type":"HNSW","metric_type":metric,"params":{"M":int(M),"efConstruction":int(efc)}})

def build_index_diskann(client, metric):
    client.create_index("bench","vec",{"index_type":"DISKANN","metric_type":metric,"params":{}})

def wait_index_ready(client, col="bench", field="vec", timeout_s=900, sleep_s=1.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            st = client.get_index_state(col, field)
            if str(st.get("state","")).lower() == "finished":
                return
        except Exception:
            pass
        time.sleep(sleep_s)
    raise TimeoutError("Milvus index build not finished")

def load_collection(client, col="bench"):
    client.load_collection(col)

def search(client, queries, topk, params):
    res = client.search("bench", data=queries.tolist(), anns_field="vec", limit=int(topk), params=params)
    idx=[]; 
    for hits in res:
        idx.append([h["id"] for h in hits])
    return np.array(idx, dtype=int)
