# bench/cpu_dockerstats.py
import docker, time

def sample_container_cpu(container_name: str, duration_s: int) -> float:
    """Return average container CPU % over duration (docker stats compatible)."""
    client = docker.from_env()
    c = client.containers.get(container_name)
    stats = c.stats(stream=True)
    total = 0; n = 0
    start = time.time()
    for s in stats:
        cpu = s["cpu_stats"]["cpu_usage"]["total_usage"]
        sys = s["cpu_stats"]["system_cpu_usage"]
        pcpu = s.get("precpu_stats", {})
        p_cpu = pcpu.get("cpu_usage", {}).get("total_usage", cpu)
        p_sys = pcpu.get("system_cpu_usage", sys)
        cpu_delta = cpu - p_cpu
        sys_delta = (sys - p_sys) or 1
        perc = (cpu_delta / sys_delta) * len(s["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) * 100.0
        total += perc; n += 1
        if time.time()-start >= duration_s: break
    try: next(stats)
    except: pass
    return (total/n) if n else 0.0
