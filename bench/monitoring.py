# bench/monitoring.py
import os, time, json, threading, subprocess, docker
from typing import Dict

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

class IOMonitor:
    """Monitor I/O (bpftrace jika tersedia; fallback iostat)."""
    def __init__(self):
        self.monitoring = False
        self.results = {}
        self.bpftrace_proc = None
        self.duration_seconds = None

    def start_monitoring(self, duration_seconds: int = 30) -> threading.Thread:
        self.duration_seconds = duration_seconds
        def monitor():
            bpf_script = r'''
            tracepoint:block:block_rq_issue {
                @bytes_hist = hist(args->bytes);
                @total_bytes += args->bytes;
                @io_count++;
                if (args->rwbs[0] == 'R') { @read_bytes += args->bytes; @read_count++; }
                else if (args->rwbs[0] == 'W') { @write_bytes += args->bytes; @write_count++; }
            }
            END {
                printf("=== FINAL STATS ===\n");
                printf("Total bytes: %d\n", @total_bytes);
                printf("Read bytes: %d\n", @read_bytes);
                printf("Write bytes: %d\n", @write_bytes);
                printf("Total IOPS: %d\n", @io_count);
                printf("Read IOPS: %d\n", @read_count);
                printf("Write IOPS: %d\n", @write_count);
                print(@bytes_hist);
            }'''
            try:
                result = subprocess.run(['bpftrace', '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    self._iostat_fallback(duration_seconds); return
                cmd = ['bpftrace', '-e', bpf_script]
                self.bpftrace_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                      text=True, preexec_fn=os.setsid)
                try:
                    stdout, stderr = self.bpftrace_proc.communicate(timeout=duration_seconds + 5)
                    self.results['bpftrace_output'] = stdout
                    self.results['bpftrace_stderr'] = stderr
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.bpftrace_proc.pid), 15)
                    stdout, stderr = self.bpftrace_proc.communicate()
                    self.results['bpftrace_output'] = stdout
                    self.results['bpftrace_stderr'] = stderr
            except Exception:
                self._iostat_fallback(duration_seconds)
            self.monitoring = False
        self.monitoring = True
        t = threading.Thread(target=monitor, daemon=True); t.start()
        return t

    def _iostat_fallback(self, duration_seconds: int):
        try:
            cmd = ['iostat', '-x', '1', str(duration_seconds)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_seconds + 5)
            self.results['iostat_output'] = result.stdout
            self.results['iostat_stderr'] = result.stderr
        except Exception as e:
            self.results['error'] = f"iostat fallback failed: {e}"
            # Final fallback: skip I/O monitoring
            self.results['skipped'] = True

    def stop_monitoring(self):
        self.monitoring = False
        if self.bpftrace_proc and self.bpftrace_proc.poll() is None:
            try: os.killpg(os.getpgid(self.bpftrace_proc.pid), 15)
            except: pass

    def get_results(self) -> Dict:
        return self.results.copy()

    def parse_bandwidth(self) -> Dict[str, float]:
        parsed = {'read_mb': 0.0, 'write_mb': 0.0, 'total_mb': 0.0, 'avg_bandwidth_mb_s': 0.0}
        if 'skipped' in self.results:
            return parsed  # Return zeros if skipped
        if 'bpftrace_output' in self.results:
            out = self.results['bpftrace_output']
            for line in out.splitlines():
                if 'Total bytes:' in line:
                    parsed['total_mb'] = int(line.split(':',1)[1]) / (1024*1024)
                elif 'Read bytes:' in line:
                    parsed['read_mb'] = int(line.split(':',1)[1]) / (1024*1024)
                elif 'Write bytes:' in line:
                    parsed['write_mb'] = int(line.split(':',1)[1]) / (1024*1024)
            if parsed['total_mb'] and self.duration_seconds:
                parsed['avg_bandwidth_mb_s'] = parsed['total_mb'] / float(self.duration_seconds)

        elif 'iostat_output' in self.results:
            out = self.results['iostat_output']
            read_sum = write_sum = cnt = 0.0
            for line in out.splitlines():
                parts = line.split()
                if len(parts) > 10 and parts[0] != 'Device':
                    try:
                        read_kb_s = float(parts[5]); write_kb_s = float(parts[6])
                        read_sum += read_kb_s / 1024.0; write_sum += write_kb_s / 1024.0; cnt += 1.0
                    except: continue
            if cnt > 0:
                parsed['avg_bandwidth_mb_s'] = (read_sum + write_sum) / cnt
        return parsed

def run_fio_baseline(target_dir: str = "/datasets", duration: int = 30) -> Dict:
    baseline_results = {}
    tests = [
        {'name': 'random_4k_read', 'params': f'--name=rand4k --rw=randread --bs=4k --numjobs=1 --runtime=30 --time_based --size=128M'},  # Kurangi dari 256M ke 128M
        {'name': 'sequential_read', 'params': f'--name=seqread --rw=read --bs=1M --numjobs=1 --runtime=30 --time_based --direct=1 --size=256M'},
        {'name': 'random_4k_write','params': f'--name=rand4kw --rw=randwrite --bs=4k --numjobs=1 --runtime=30 --time_based --size=256M'},
    ]
    os.makedirs(target_dir, exist_ok=True)
    test_file = os.path.join(target_dir, "fio_test.tmp")
    for test in tests:
        cmd = f"fio {test['params']} --filename={test_file} --output-format=json"  # Hapus --size=1G
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=duration + 30, cwd=target_dir)
            if result.returncode == 0:
                try:
                    fio_output = json.loads(result.stdout); jobs = fio_output.get('jobs', [])
                    if jobs:
                        job = jobs[0]; rd = job.get('read', {}); wr = job.get('write', {})
                        baseline_results[test['name']] = {
                            'read_iops': rd.get('iops', 0), 'read_bw_mb': rd.get('bw', 0) / 1024,
                            'read_latency_us': rd.get('lat_ns', {}).get('mean', 0) / 1000,
                            'write_iops': wr.get('iops', 0), 'write_bw_mb': wr.get('bw', 0) / 1024,
                            'write_latency_us': wr.get('lat_ns', {}).get('mean', 0) / 1000,
                        }
                except json.JSONDecodeError:
                    baseline_results[test['name']] = {'error': 'Failed to parse fio JSON output'}
            else:
                baseline_results[test['name']] = {'error': f'fio failed: {result.stderr}'}
        except subprocess.TimeoutExpired:
            baseline_results[test['name']] = {'error': 'fio timeout'}
        except Exception as e:
            baseline_results[test['name']] = {'error': f'fio exception: {e}'}
    try: os.remove(test_file)
    except: pass
    return baseline_results

def flush_page_cache():
    cmds = [
        "sync",
        "echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true",
        "echo 2 > /proc/sys/vm/drop_caches 2>/dev/null || true",
        "echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true",
    ]
    for cmd in cmds:
        try: subprocess.run(cmd, shell=True, timeout=10); time.sleep(0.5)
        except: pass
    print("Page cache flush attempted")