#!/usr/bin/env python3
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_search_callable():
    # Mock search function
    def mock_search(batch, topk, ef_search):
        time.sleep(0.001)  # 1ms simulated
        return []
    
    def search_callable(qs, secs, conc):
        stop_at = time.time() + secs
        chunks = np.array_split(qs, conc)
        all_latencies = []
        
        def worker(batch):
            done = 0
            worker_latencies = []
            while time.time() < stop_at:
                t_start = time.time()
                _ = mock_search(batch, 10, 64)
                t_end = time.time()
                worker_latencies.append(t_end - t_start)
                done += len(batch)
            return done, worker_latencies
            
        total = 0
        with ThreadPoolExecutor(max_workers=conc) as ex:
            futs = [ex.submit(worker, b) for b in chunks if len(b) > 0]
            for fu in as_completed(futs):
                worker_total, worker_latencies = fu.result()
                total += worker_total
                all_latencies.extend(worker_latencies)
        
        return total / float(secs), all_latencies

    # Test
    queries = np.random.rand(100, 768)
    result = search_callable(queries, 2, 1)
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
    
    if isinstance(result, tuple) and len(result) == 2:
        qps, latencies = result
        print(f'QPS: {qps}')
        print(f'Latencies: {len(latencies)} samples')
        if latencies:
            print(f'P99: {np.percentile(latencies, 99)*1000:.2f}ms')
    else:
        print("Unexpected result format")

if __name__ == "__main__":
    test_search_callable()