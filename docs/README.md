# eBPF GPU Observability

> **KubeCon Europe 2026** · *Hacking GPU Observability: eBPF & Ephemeral Containers in Action on Kubernetes* · Brandon Kang, Akamai Technologies

Real-time GPU telemetry for Kubernetes AI/ML workloads using **eBPF uprobes** and **ephemeral containers** — without modifying production images or disrupting running Pods.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](./architecture.md)
- [Deployment Guide](./deployment.md)
- [AI Context / Agent Instructions](./ai-context.md)
- [Ephemeral Container Debugging](./ephemeral-debugging.md)

---

## Overview

Modern AI/ML stacks run GPU workloads at scale on Kubernetes. Observing and securing these workloads is hard:

- You can't modify production container images to add instrumentation.
- Traditional GPU monitoring (DCGM, NSight) is coarse or too invasive for production.
- CUDA API behaviour is asynchronous and opaque from the outside.

This project demonstrates how to solve all three problems using two native Kubernetes primitives:

| Technique | Purpose |
|---|---|
| **eBPF uprobes** on `libcudart.so` | Intercept `cudaMalloc`, `cudaLaunchKernel` at the kernel level — zero code changes |
| **Ephemeral Containers** | Inject a live debug environment into running pods using `kubectl debug` |

### Key Metrics Collected

| Metric | Description |
|---|---|
| `gpu_cuda_allocated_bytes` | GPU VRAM allocated per workload / PID |
| `gpu_cuda_kernel_launches_total` | Counter of kernel launches per workload |
| `gpu_kernel_duration_seconds` | Histogram of kernel execution latency |
| `gpu_utilization_percent` | GPU compute utilisation (0-100%) |
| `gpu_memory_used_bytes` | Total VRAM used |
| `gpu_cuda_errors_total` | CUDA API errors by type |

### Stack

```
libcudart.so uprobes (eBPF)
    │
    ▼
gpu-tracer DaemonSet  ──► :8000/metrics
    │
    ▼
Prometheus (pod discovery, 5s scrape)
    │
    ▼
Grafana (LoadBalancer, public URL)
```

---

## Quick Start

```bash
# 1. Deploy entire stack
kubectl apply -f manifests/deploy-all.yaml --kubeconfig=<your-kubeconfig>

# 2. Get the Grafana public URL
kubectl get svc grafana -n gpu-observability

# 3. Open in browser — anonymous access enabled
open http://<EXTERNAL-IP>/d/ebpf-gpu-obs/ebpf-gpu-observability
```

> **Login** (admin): `admin` / `kubecon2026`

---

## Project Structure

```
.
├── agent/
│   ├── bpf/tracer.c          # eBPF C program (CO-RE, uprobes on CUDA API)
│   ├── main.go               # Go loader using cilium/ebpf
│   ├── mock_agent/           # Python mock agent for demo without GPU HW
│   ├── Dockerfile            # Multi-stage: clang (BPF) + Go build
│   └── Makefile
├── manifests/
│   ├── deploy-all.yaml       # Single-file deployment of full stack
│   ├── agent-daemonset.yaml  # Standalone agent DaemonSet
│   ├── prometheus.yaml       # Prometheus + RBAC
│   ├── grafana.yaml          # Grafana + provisioning ConfigMaps
│   └── dashboard.yaml        # Grafana dashboard JSON ConfigMap
├── workload/
│   ├── dummy_gpu.py          # CUDA-calling Python workload for demo
│   └── Dockerfile
├── docs/                     # ← You are here
└── README.md
```
