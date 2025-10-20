# bench/monitoring.py
import os, time, json, threading, subprocess
try:
    import docker
except ImportError:
    docker = None
try:
    import psutil
except ImportError:
    psutil = None
from typing import Dict

def sample_container_cpu(container_name: str, duration_s: int) -> float:
    """Return average container CPU % over duration (docker stats compatible, fallback to psutil)."""
    if docker:
        try:
            client = docker.from_env()
            c = client.containers.get(container_name)
            
            # Get initial stats
            stats1 = c.stats(stream=False)
            cpu1 = stats1["cpu_stats"]["cpu_usage"]["total_usage"]
            sys1 = stats1["cpu_stats"]["system_cpu_usage"]
            online_cpus = stats1["cpu_stats"]["online_cpus"]
            
            time.sleep(duration_s)
            
            # Get final stats
            stats2 = c.stats(stream=False)
            cpu2 = stats2["cpu_stats"]["cpu_usage"]["total_usage"]
            sys2 = stats2["cpu_stats"]["system_cpu_usage"]
            
            # Calculate CPU percentage
            cpu_delta = cpu2 - cpu1
            sys_delta = sys2 - sys1
            
            if sys_delta > 0:
                cpu_percent = (cpu_delta / sys_delta) * online_cpus * 100.0
                return max(0.0, cpu_percent)  # Ensure non-negative
            else:
                return 0.0
                
        except Exception as e:
            print(f"Docker stats failed: {e}, falling back to psutil")

    # Fallback to psutil for CPU monitoring
    if psutil:
        try:
            start_time = time.time()
            start_cpu = psutil.cpu_percent(interval=None)
            time.sleep(duration_s)
            end_cpu = psutil.cpu_percent(interval=None)
            return (start_cpu + end_cpu) / 2.0
        except Exception as e:
            print(f"psutil CPU monitoring failed: {e}")
    return 0.0

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
                if (args->rwbs[0] == "R") { @read_bytes += args->bytes; @read_count++; }
                else if (args->rwbs[0] == "W") { @write_bytes += args->bytes; @write_count++; }
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
                    if self.bpftrace_proc.returncode != 0:
                        print(f"I/O monitoring: bpftrace failed with returncode {self.bpftrace_proc.returncode}, falling back to iostat")
                        self._iostat_fallback(duration_seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.bpftrace_proc.pid), 15)
                    stdout, stderr = self.bpftrace_proc.communicate()
                    self.results['bpftrace_output'] = stdout
                    self.results['bpftrace_stderr'] = stderr
                    print(f"I/O monitoring: bpftrace timed out, falling back to iostat")
                    self._iostat_fallback(duration_seconds)
            except Exception as e:
                print(f"I/O monitoring: bpftrace failed ({e}), falling back to iostat")
                self._iostat_fallback(duration_seconds)
            self.monitoring = False
        self.monitoring = True
        t = threading.Thread(target=monitor, daemon=True); t.start()
        return t

    def _iostat_fallback(self, duration_seconds: int):
        print(f"I/O monitoring: Starting iostat fallback for {duration_seconds}s")
        self.duration_seconds = duration_seconds  # Ensure duration is set
        try:
            # macOS iostat doesn't support -x, use -d for disk stats
            import platform
            system = platform.system()
            print(f"I/O monitoring: Detected platform: {system}")
            if system == 'Darwin':  # macOS
                cmd = ['iostat', '-d', '1', str(duration_seconds)]
            else:  # Linux
                cmd = ['iostat', '-d', '1', str(duration_seconds)]  # Simplified for container
            print(f"I/O monitoring: Running iostat command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_seconds + 5)
            print(f"I/O monitoring: iostat returncode: {result.returncode}")
            self.results['iostat_output'] = result.stdout
            self.results['iostat_stderr'] = result.stderr
            print(f"I/O monitoring: iostat completed, output length: {len(result.stdout)}")
            if result.stderr:
                print(f"I/O monitoring: iostat stderr: {result.stderr}")
        except Exception as e:
            print(f"iostat fallback failed: {e}, trying psutil")
            import traceback
            traceback.print_exc()
            self._psutil_fallback(duration_seconds)

    def _psutil_fallback(self, duration_seconds: int):
        """Fallback I/O monitoring using psutil disk I/O counters."""
        if not psutil:
            self.results['error'] = "psutil not available"
            self.results['skipped'] = True
            return

        try:
            start_counters = psutil.disk_io_counters()
            time.sleep(duration_seconds)
            end_counters = psutil.disk_io_counters()

            if start_counters and end_counters:
                read_bytes = end_counters.read_bytes - start_counters.read_bytes
                write_bytes = end_counters.write_bytes - start_counters.write_bytes
                total_bytes = read_bytes + write_bytes

                self.results['psutil_output'] = {
                    'read_bytes': read_bytes,
                    'write_bytes': write_bytes,
                    'total_bytes': total_bytes,
                    'read_count': end_counters.read_count - start_counters.read_count,
                    'write_count': end_counters.write_count - start_counters.write_count,
                    'duration': duration_seconds
                }
            else:
                self.results['error'] = "psutil disk counters not available"
                self.results['skipped'] = True
        except Exception as e:
            self.results['error'] = f"psutil fallback failed: {e}"
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
        
        try:
            # Check for valid bpftrace output first
            has_valid_bpftrace = ('bpftrace_output' in self.results and 
                                 self.results['bpftrace_output'].strip() and
                                 'Total bytes:' in self.results['bpftrace_output'])
            
            if has_valid_bpftrace:
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
                import platform
                if platform.system() == 'Darwin':  # macOS format: disk0 KB/t tps MB/s
                    lines = out.splitlines()
                    for line in lines[2:]:  # Skip first 2 header lines
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                mb_s = float(parts[2])  # MB/s is index 2
                                read_sum += mb_s / 2.0  # Assume 50/50 split
                                write_sum += mb_s / 2.0
                                cnt += 1.0
                            except (ValueError, IndexError) as e:
                                continue
                else:  # Linux format in container
                    for line in out.splitlines():
                        parts = line.split()
                        if len(parts) > 6 and parts[0] not in ['Device', 'Linux', ''] and not parts[0].startswith('(') and not parts[0].startswith('_'):
                            try:
                                read_kb_s = float(parts[2])   # kB_read/s index 2
                                write_kb_s = float(parts[3])  # kB_wrtn/s index 3
                                read_sum += read_kb_s / 1024.0  # Convert to MB/s
                                write_sum += write_kb_s / 1024.0
                                cnt += 1.0
                            except (ValueError, IndexError) as e:
                                continue
                
                if cnt > 0:
                    avg_read_mb_s = read_sum / cnt
                    avg_write_mb_s = write_sum / cnt
                    parsed['read_mb'] = avg_read_mb_s * self.duration_seconds
                    parsed['write_mb'] = avg_write_mb_s * self.duration_seconds
                    parsed['total_mb'] = (avg_read_mb_s + avg_write_mb_s) * self.duration_seconds
                    parsed['avg_bandwidth_mb_s'] = avg_read_mb_s + avg_write_mb_s

            elif 'psutil_output' in self.results:
                psutil_data = self.results['psutil_output']
                parsed['read_mb'] = psutil_data['read_bytes'] / (1024 * 1024)
                parsed['write_mb'] = psutil_data['write_bytes'] / (1024 * 1024)
                parsed['total_mb'] = psutil_data['total_bytes'] / (1024 * 1024)
                if psutil_data['duration'] > 0:
                    parsed['avg_bandwidth_mb_s'] = parsed['total_mb'] / psutil_data['duration']
                
        except Exception as e:
            # Return zeros on exception instead of crashing
            return {'read_mb': 0.0, 'write_mb': 0.0, 'total_mb': 0.0, 'avg_bandwidth_mb_s': 0.0}

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