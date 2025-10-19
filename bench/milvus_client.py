# bench/milvus_client.py
from pymilvus import MilvusClient, DataType
from pymilvus.milvus_client.index import IndexParams
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
        "dimension": dim,
        "fields": [
            {"name":"id","dtype":DataType.INT64,"is_primary":True,"auto_id":True},
            {"name":"vec","dtype":DataType.FLOAT_VECTOR,"dim":dim}
        ],
        "metric_type": metric
    }

def drop_recreate(client, dim, metric):
    if client.has_collection("bench"): 
        client.drop_collection("bench")
    
    # Use the simplest possible approach - just create with dimension
    client.create_collection(
        collection_name="bench",
        dimension=dim
    )

def insert_and_flush(client, vectors, batch=5000):
    N=len(vectors); off=0
    while off < N:
        batch_vectors = vectors[off:off+batch].tolist()
        # Include both id (manual) and vector data
        data = [{"id": off + i, "vector": vec} for i, vec in enumerate(batch_vectors)]
        client.insert("bench", data=data)
        off += batch
    client.flush("bench")

def build_index_ivf(client, n, metric, nlist):
    # Release (unload) collection first, then drop existing indexes
    try:
        client.release_collection("bench")
        indexes = client.list_indexes("bench")
        for index_name in indexes:
            client.drop_index(collection_name="bench", index_name=index_name)
    except Exception as e:
        print(f"Warning: Could not drop existing indexes: {e}")
        
    index_params = IndexParams()
    index_params.add_index(
        field_name="vector",
        index_type="IVF_FLAT",
        metric_type=metric,
        nlist=int(nlist)
    )
    client.create_index(collection_name="bench", index_params=index_params)

def build_index_hnsw(client, metric, M, efc):
    index_params = IndexParams()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type=metric,
        M=int(M),
        efConstruction=int(efc)
    )
    client.create_index(collection_name="bench", index_params=index_params)

def build_index_diskann(client, metric):
    index_params = IndexParams()
    index_params.add_index(
        field_name="vector",
        index_type="DISKANN",
        metric_type=metric
    )
    client.create_index(collection_name="bench", index_params=index_params)

def wait_index_ready(client, col="bench", field="vector", timeout_s=120, sleep_s=2.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            st = client.get_index_state(col, field)
            state = str(st.get("state","")).lower()
            print(f"Index state: {state}")
            if state == "finished":
                return
            elif state == "failed":
                raise RuntimeError(f"Index build failed: {st}")
        except Exception as e:
            print(f"Error checking index state: {e}")
        time.sleep(sleep_s)
    raise TimeoutError("Milvus index build not finished")

def load_collection(client, col="bench"):
    client.load_collection(col)

def search(client, queries, topk, params):
    res = client.search("bench", data=queries.tolist(), anns_field="vector", limit=int(topk), params=params)
    idx=[]; 
    for hits in res:
        idx.append([h["id"] for h in hits])
    return np.array(idx, dtype=int)
