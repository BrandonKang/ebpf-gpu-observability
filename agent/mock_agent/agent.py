"""
Mock GPU Observability Agent
----------------------------
Simulates what the real eBPF agent would report: CUDA kernel launches
and memory allocation events captured via uprobes on libcudart.so.

In the real system, these metrics would be emitted by a privileged DaemonSet
running a Go/cilium-ebpf program. For the demo, this script generates
realistic-looking fake data so Grafana has real charts to display.
"""

import time
import random
import math
from prometheus_client import start_http_server, Gauge, Counter, Histogram

# --- Prometheus Metrics (mirror what the real eBPF agent emits) ---

CUDA_ALLOCATED_BYTES = Gauge(
    "gpu_cuda_allocated_bytes",
    "Total bytes currently allocated on GPU via cudaMalloc (per workload)",
    ["pid", "workload"],
)

CUDA_KERNEL_LAUNCHES = Counter(
    "gpu_cuda_kernel_launches_total",
    "Total cudaLaunchKernel calls (per workload)",
    ["pid", "workload"],
)

GPU_UTILIZATION = Gauge(
    "gpu_utilization_percent",
    "GPU compute utilization percentage (0-100)",
    ["gpu_id"],
)

GPU_MEMORY_USED_BYTES = Gauge(
    "gpu_memory_used_bytes",
    "GPU VRAM currently in use (bytes)",
    ["gpu_id"],
)

GPU_MEMORY_TOTAL_BYTES = Gauge(
    "gpu_memory_total_bytes",
    "Total GPU VRAM available (bytes)",
    ["gpu_id"],
)

CUDA_ERROR_COUNT = Counter(
    "gpu_cuda_errors_total",
    "Total CUDA API errors observed",
    ["error_code", "workload"],
)

KERNEL_DURATION = Histogram(
    "gpu_kernel_duration_seconds",
    "Duration of CUDA kernel execution",
    ["workload"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

# --- Simulated Workloads ---

WORKLOADS = [
    {"name": "llm-inference",  "pid": "1142", "gpu_id": "0", "alloc_mb": 8192},
    {"name": "training-job",   "pid": "1387", "gpu_id": "0", "alloc_mb": 16384},
    {"name": "feature-server", "pid": "2048", "gpu_id": "1", "alloc_mb": 2048},
]

GPU_TOTAL_MEMORY_MB = 24576  # 24 GB GPU (e.g. NVIDIA A4000)

# Set static totals
for gpu_id in ["0", "1"]:
    GPU_MEMORY_TOTAL_BYTES.labels(gpu_id=gpu_id).set(GPU_TOTAL_MEMORY_MB * 1024 * 1024)

# Initialise allocations so we never go negative
for wl in WORKLOADS:
    CUDA_ALLOCATED_BYTES.labels(pid=wl["pid"], workload=wl["name"]).set(
        wl["alloc_mb"] * 1024 * 1024
    )

tick = 0

def simulate():
    global tick
    tick += 1
    t = tick

    total_used = {gid: 0 for gid in ["0", "1"]}

    for wl in WORKLOADS:
        pid, name, gid = wl["pid"], wl["name"], wl["gpu_id"]
        base_mb = wl["alloc_mb"]

        # Allocation fluctuates over a sine wave ±15%
        multiplier = 1 + 0.15 * math.sin(t * 0.1 + hash(name) % 10)
        alloc_bytes = base_mb * 1024 * 1024 * multiplier
        CUDA_ALLOCATED_BYTES.labels(pid=pid, workload=name).set(alloc_bytes)
        total_used[gid] += alloc_bytes

        # Kernel launches: Poisson-like – 1-12 per tick
        launches = random.randint(1, 12) if name != "feature-server" else random.randint(0, 4)
        for _ in range(launches):
            CUDA_KERNEL_LAUNCHES.labels(pid=pid, workload=name).inc()
            duration = random.expovariate(1 / 0.03)  # mean ~30ms
            KERNEL_DURATION.labels(workload=name).observe(duration)

        # Occasional CUDA errors (very rare)
        if random.random() < 0.005:
            CUDA_ERROR_COUNT.labels(error_code="cudaErrorIllegalAccess", workload=name).inc()

    for gid, used in total_used.items():
        total = GPU_TOTAL_MEMORY_MB * 1024 * 1024
        used_capped = min(used, total * 0.95)
        GPU_MEMORY_USED_BYTES.labels(gpu_id=gid).set(used_capped)

        # Utilisation: correlated with kernel launches this tick
        utilisation = min(95, 30 + (t % 60) * 1.1 + random.gauss(0, 5))
        GPU_UTILIZATION.labels(gpu_id=gid).set(utilisation)

if __name__ == "__main__":
    port = 8000
    start_http_server(port)
    print(f"Mock GPU metrics agent running on :{port}/metrics", flush=True)

    while True:
        simulate()
        time.sleep(2)
