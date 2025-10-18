import weaviate, numpy as np, time

def connect():
    return weaviate.Client("http://weaviate:8080")

def drop_recreate(client, classname, dim, metric):
    if client.schema.exists(classname):
        client.schema.delete_class(classname)
    cls = {
      "class": classname,
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {"distance": metric, "efConstruction": 200, "maxConnections": 16},
      "properties": [{"name":"pid","dataType":["int"]}],
    }
    client.schema.create_class(cls)

def insert(client, classname, vectors, batch=2000):
    with client.batch(batch_size=batch) as b:
        for i, v in enumerate(vectors):
            b.add_data_object({"pid": int(i)}, class_name=classname, vector=v.tolist())

def search(client, classname, queries, topk, ef=64):
    res=[]
    for q in queries:
        r = (client.query.get(classname, ["pid"])
             .with_near_vector({"vector": q.tolist()})
             .with_limit(topk).do())
        objs = r.get("data",{}).get("Get",{}).get(classname,[]) or []
        ids = [int(o["pid"]) for o in objs]
        res.append(ids)
    return np.array(res, dtype=int)
