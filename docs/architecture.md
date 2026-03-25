# Architecture

## System Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Kubernetes Node (LKE / any cloud)                                          │
│                                                                              │
│  ┌─────────────────────────────────┐                                        │
│  │  GPU Workload Pod               │                                        │
│  │  ┌───────────────────────────┐  │                                        │
│  │  │  application container    │  │                                        │
│  │  │  └─► libcudart.so         │  │                                        │
│  │  │       cudaMalloc()  ◄──── │──│────── eBPF uprobe (kernel space)      │
│  │  │       cudaLaunchKernel() ◄─│──│────── eBPF uprobe (kernel space)      │
│  │  └───────────────────────────┘  │                                        │
│  │                                  │                                        │
│  │  ┌───────────────────────────┐  │   ┌────────────────────────────────┐  │
│  │  │  Ephemeral Debug Container│  │   │  gpu-tracer (DaemonSet pod)    │  │
│  │  │  kubectl debug ...        │  │   │  ┌────────────────────────────┐│  │
│  │  │  ┌─────────────────────┐ │  │   │  │ cilium/ebpf loader (Go)    ││  │
│  │  │  │ strace, bpftrace,   │ │  │   │  │ BPF maps poll loop         ││  │
│  │  │  │ nsenter, perf       │ │  │   │  │ Prometheus exporter :8000  ││  │
│  │  │  └─────────────────────┘ │  │   │  └────────────────────────────┘│  │
│  │  └───────────────────────────┘  │   └──────────────┬─────────────────┘  │
│  └─────────────────────────────────┘                  │ :8000/metrics       │
│                                                         │                    │
└─────────────────────────────────────────────────────────┼────────────────────┘
                                                           │
                                              ┌────────────▼──────────────────┐
                                              │ Prometheus (5s scrape)         │
                                              └────────────┬──────────────────┘
                                                           │
                                              ┌────────────▼──────────────────┐
                                              │ Grafana (LoadBalancer, port 80)│
                                              │ Public IP → Dashboard          │
                                              └───────────────────────────────┘
```

---

## Component Details

### 1. eBPF Agent (`agent/`)

The **production** agent is written in Go using [cilium/ebpf](https://github.com/cilium/ebpf) with **CO-RE (Compile Once – Run Everywhere)** via BTF.

**Why CO-RE instead of Python/BCC?**

| | BCC (Python) | cilium/ebpf CO-RE (Go) |
|---|---|---|
| Kernel headers required at runtime | ✅ Yes | ❌ No |
| Works on LKE (no pre-built headers) | ❌ No | ✅ Yes |
| Binary size | Large (BCC + Python) | Small (static Go binary) |
| Production-safe | ❌ Risky | ✅ Yes |

**How it works:**

1. `bpf/tracer.c` is compiled by `clang` into a BTF-annotated BPF ELF file at image build time.
2. `go generate` uses `bpf2go` to embed the ELF as a Go byte slice at compile time.
3. At runtime the Go binary loads the BPF programs via `cilium/ebpf`, attaches uprobes to `libcudart.so` functions (`cudaMalloc`, `cudaLaunchKernel`), and polls BPF hash maps every 2s.
4. Maps are converted to Prometheus `Gauge` / `Counter` metrics and exposed on `:8000/metrics`.

**The BPF program captures:**
- `PT_REGS_PARM2` (size arg of `cudaMalloc`) → allocation bytes
- Hit count for `cudaLaunchKernel` → kernel launches

### 2. Mock Agent (`agent/mock_agent/`)

For the demo/conference environment (no physical GPU available), the mock agent runs as a **Python** service simulating realistic GPU activity patterns:
- Sine-wave VRAM allocations per workload
- Poisson-distributed kernel launch rates
- Histograms for kernel execution latency
- Occasional random CUDA errors

All exported metric names are identical to the real agent.

### 3. Prometheus

Standard Prometheus deployment with **Kubernetes pod SD** using annotation-based discovery:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
```

Prometheus discovers all `gpu-tracer` pods using the Kubernetes API (RBAC ClusterRole granted).

### 4. Grafana

Grafana with provisioned datasource and dashboard.  
Exposed via a Kubernetes **LoadBalancer** service on port 80 (LKE provisions a NodeBalancer automatically).  
Anonymous viewer access enabled for public demos.

---

## Data Flow

```
cudaMalloc() call in GPU workload
  │
  ▼
eBPF uprobe fires (kernel context)
  │   Reads: PID (tgid), size arg (PT_REGS_PARM2)
  ▼
BPF hash map: {pid → cumulative_bytes}
  │
  ▼ (polled every 2s by Go userspace)
Prometheus Gauge: gpu_cuda_allocated_bytes{pid,workload}
  │
  ▼ (scraped every 5s)
Prometheus TSDB
  │
  ▼ (Grafana queries on 5s refresh)
Dashboard panel: "CUDA Bytes Allocated by Workload"
```

---

## Security Model

The agent `DaemonSet` requires elevated privileges to load BPF programs:

```yaml
securityContext:
  privileged: true
  capabilities:
    add: ["SYS_ADMIN", "BPF", "PERFMON"]
```

For production hardening:
- Use `BPF` + `PERFMON` capabilities only (drop `SYS_ADMIN`).
- Enable Kubernetes `PodSecurityAdmission` with a custom policy.
- Use `cilium/tetragon` for zero-trust enforcement on top of the telemetry.
