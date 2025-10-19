# bench/weaviate_client.py
import weaviate, numpy as np

def connect():
    return weaviate.Client("http://weaviate:8080")

def drop_recreate(client, classname, dim, metric, ef=None):
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

def insert(client, classname, vectors, batch=2000):
    with client.batch(batch_size=batch) as b:
        for i, v in enumerate(vectors):
            b.add_data_object({"pid": int(i)}, class_name=classname, vector=v.tolist())

def search(client, classname, queries, topk, ef=64, hybrid=False, query_texts=None):
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
