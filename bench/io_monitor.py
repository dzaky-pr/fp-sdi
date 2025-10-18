import os
import time
import json
import threading
import subprocess
from typing import Dict, List, Optional

class IOMonitor:
    """Monitor I/O operations using bpftrace for block-level analysis"""
    
    def __init__(self):
        self.monitoring = False
        self.results = {}
        self.bpftrace_proc = None
        
    def start_monitoring(self, duration_seconds: int = 30) -> threading.Thread:
        """Start I/O monitoring in background thread"""
        def monitor():
            # bpftrace script for block I/O monitoring
            bpf_script = '''
            tracepoint:block:block_rq_issue {
                @bytes_hist = hist(args->bytes);
                @total_bytes += args->bytes;
                @io_count++;
                if (args->rwbs[0] == 'R') {
                    @read_bytes += args->bytes;
                    @read_count++;
                } else if (args->rwbs[0] == 'W') {
                    @write_bytes += args->bytes;
                    @write_count++;
                }
            }
            
            interval:s:1 {
                @bandwidth_mbs = @total_bytes / (1024*1024);
                @read_mbs = @read_bytes / (1024*1024);
                @write_mbs = @write_bytes / (1024*1024);
                time("%H:%M:%S ");
                printf("Total: %d MB, Read: %d MB, Write: %d MB, IOPS: %d\\n", 
                       @bandwidth_mbs, @read_mbs, @write_mbs, @io_count);
            }
            
            END {
                printf("\\n=== FINAL STATS ===\\n");
                printf("Total bytes: %d\\n", @total_bytes);
                printf("Read bytes: %d\\n", @read_bytes);
                printf("Write bytes: %d\\n", @write_bytes);
                printf("Total IOPS: %d\\n", @io_count);
                printf("Read IOPS: %d\\n", @read_count);
                printf("Write IOPS: %d\\n", @write_count);
                print(@bytes_hist);
            }
            '''
            
            try:
                # Check if bpftrace is available and we have permissions
                result = subprocess.run(['bpftrace', '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    print("bpftrace not available, using iostat fallback")
                    self._iostat_fallback(duration_seconds)
                    return
                    
                # Run bpftrace
                cmd = ['bpftrace', '-e', bpf_script]
                self.bpftrace_proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    text=True, preexec_fn=os.setsid
                )
                
                # Wait for completion or timeout
                try:
                    stdout, stderr = self.bpftrace_proc.communicate(timeout=duration_seconds + 5)
                    self.results['bpftrace_output'] = stdout
                    self.results['bpftrace_stderr'] = stderr
                except subprocess.TimeoutExpired:
                    # Kill the process group
                    os.killpg(os.getpgid(self.bpftrace_proc.pid), 15)
                    stdout, stderr = self.bpftrace_proc.communicate()
                    self.results['bpftrace_output'] = stdout
                    self.results['bpftrace_stderr'] = stderr
                    
            except Exception as e:
                print(f"bpftrace failed: {e}, using iostat fallback")
                self._iostat_fallback(duration_seconds)
                
            self.monitoring = False
            
        self.monitoring = True
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        return monitor_thread
        
    def _iostat_fallback(self, duration_seconds: int):
        """Fallback I/O monitoring using iostat"""
        try:
            cmd = ['iostat', '-x', '1', str(duration_seconds)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_seconds + 5)
            self.results['iostat_output'] = result.stdout
            self.results['iostat_stderr'] = result.stderr
        except Exception as e:
            self.results['error'] = f"iostat fallback failed: {e}"
            
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.bpftrace_proc and self.bpftrace_proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.bpftrace_proc.pid), 15)
            except:
                pass
                
    def get_results(self) -> Dict:
        """Get monitoring results"""
        return self.results.copy()
        
    def parse_bandwidth(self) -> Dict[str, float]:
        """Parse bandwidth from results"""
        parsed = {'read_mb': 0, 'write_mb': 0, 'total_mb': 0, 'avg_bandwidth_mb_s': 0}
        
        if 'bpftrace_output' in self.results:
            output = self.results['bpftrace_output']
            # Extract final stats
            lines = output.split('\n')
            for line in lines:
                if 'Total bytes:' in line:
                    total_bytes = int(line.split(':')[1].strip())
                    parsed['total_mb'] = total_bytes / (1024*1024)
                elif 'Read bytes:' in line:
                    read_bytes = int(line.split(':')[1].strip())
                    parsed['read_mb'] = read_bytes / (1024*1024)
                elif 'Write bytes:' in line:
                    write_bytes = int(line.split(':')[1].strip())
                    parsed['write_mb'] = write_bytes / (1024*1024)
                    
        elif 'iostat_output' in self.results:
            # Parse iostat output for bandwidth estimates
            # This is a simplified parser for demonstration
            output = self.results['iostat_output']
            # Parse iostat MB/s values (simplified)
            lines = output.split('\n')
            read_sum, write_sum, count = 0, 0, 0
            for line in lines:
                if 'kB_read/s' in line or 'MB_read/s' in line:
                    continue  # header
                parts = line.split()
                if len(parts) > 10 and parts[0] != 'Device':
                    try:
                        # Simplified parsing - actual iostat format may vary
                        read_kb_s = float(parts[5])  # kB_read/s column (approximate)
                        write_kb_s = float(parts[6])  # kB_wrtn/s column (approximate)
                        read_sum += read_kb_s / 1024  # Convert to MB/s
                        write_sum += write_kb_s / 1024
                        count += 1
                    except (ValueError, IndexError):
                        continue
            if count > 0:
                parsed['avg_bandwidth_mb_s'] = (read_sum + write_sum) / count
                
        return parsed


def run_fio_baseline(target_dir: str = "/datasets", duration: int = 30) -> Dict:
    """Run fio baseline tests for SSD performance"""
    
    baseline_results = {}
    
    # Test configurations
    tests = [
        {
            'name': 'random_4k_read',
            'params': '--name=rand4k --rw=randread --bs=4k --numjobs=1 --runtime={} --time_based --direct=1'.format(duration)
        },
        {
            'name': 'sequential_read', 
            'params': '--name=seqread --rw=read --bs=1M --numjobs=1 --runtime={} --time_based --direct=1'.format(duration)
        },
        {
            'name': 'random_4k_write',
            'params': '--name=rand4kw --rw=randwrite --bs=4k --numjobs=1 --runtime={} --time_based --direct=1'.format(duration)
        }
    ]
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    test_file = os.path.join(target_dir, "fio_test.tmp")
    
    for test in tests:
        print(f"Running fio {test['name']}...")
        cmd = f"fio {test['params']} --filename={test_file} --size=1G --output-format=json"
        
        try:
            result = subprocess.run(
                cmd.split(), 
                capture_output=True, 
                text=True, 
                timeout=duration + 30,
                cwd=target_dir
            )
            
            if result.returncode == 0:
                try:
                    fio_output = json.loads(result.stdout)
                    jobs = fio_output.get('jobs', [])
                    if jobs:
                        job = jobs[0]
                        read_stats = job.get('read', {})
                        write_stats = job.get('write', {})
                        
                        baseline_results[test['name']] = {
                            'read_iops': read_stats.get('iops', 0),
                            'read_bw_mb': read_stats.get('bw', 0) / 1024,  # Convert KB/s to MB/s
                            'read_latency_us': read_stats.get('lat_ns', {}).get('mean', 0) / 1000,
                            'write_iops': write_stats.get('iops', 0),
                            'write_bw_mb': write_stats.get('bw', 0) / 1024,
                            'write_latency_us': write_stats.get('lat_ns', {}).get('mean', 0) / 1000,
                        }
                except json.JSONDecodeError:
                    baseline_results[test['name']] = {'error': 'Failed to parse fio JSON output'}
            else:
                baseline_results[test['name']] = {'error': f'fio failed: {result.stderr}'}
                
        except subprocess.TimeoutExpired:
            baseline_results[test['name']] = {'error': 'fio timeout'}
        except Exception as e:
            baseline_results[test['name']] = {'error': f'fio exception: {e}'}
    
    # Cleanup
    try:
        os.remove(test_file)
    except:
        pass
        
    return baseline_results


def flush_page_cache():
    """Flush page cache before experiments"""
    commands = [
        "sync",
        "echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true",
        "echo 2 > /proc/sys/vm/drop_caches 2>/dev/null || true", 
        "echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true"
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd, shell=True, timeout=10)
            time.sleep(0.5)
        except:
            pass  # Continue even if flush fails (permission issues)
    
    print("Page cache flush attempted")