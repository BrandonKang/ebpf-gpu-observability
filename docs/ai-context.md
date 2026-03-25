# AI Context & Agent Instructions

> This document provides context for AI coding assistants (Copilot, Gemini, Claude, etc.) working on this repository.

---

## Project Summary

**ebpf-gpu-observability** is a Kubernetes-native GPU observability demo using:
- **eBPF uprobes** to trace `libcudart.so` API calls (`cudaMalloc`, `cudaLaunchKernel`) at the kernel level
- **cilium/ebpf** (Go, CO-RE) for portable, header-free BPF program loading
- **Ephemeral Containers** (`kubectl debug`) for live pod debugging without production disruption
- **Prometheus + Grafana** for metrics collection and visualisation

This was built for [KubeCon Europe 2026](https://kccnceu2026.sched.com/) — talk: *"Hacking GPU Observability: eBPF & Ephemeral Containers in Action on Kubernetes"* by Brandon Kang, Akamai Technologies.

---

## Codebase Map

```
agent/
  bpf/tracer.c         BPF C program (eBPF uprobes, CO-RE)
  main.go              Go entrypoint — loads BPF, exports Prometheus metrics
  go.mod               Dependencies: cilium/ebpf, prometheus/client_golang
  Dockerfile           Multi-stage: clang BPF compile → Go build → alpine runtime
  Makefile             make generate / build / push
  mock_agent/
    agent.py           Python mock: simulates CUDA API events for demos
    Dockerfile         python:3.11-slim + prometheus_client

manifests/
  deploy-all.yaml      Single-file full-stack deploy (use this for demos)
  agent-daemonset.yaml Standalone DaemonSet for real eBPF agent
  prometheus.yaml      Prometheus Deployment, Service, ConfigMap, RBAC
  grafana.yaml         Grafana Deployment + LoadBalancer Service
  dashboard.yaml       Grafana dashboard JSON ConfigMap
  workload-deployment.yaml  Dummy GPU workload for testing

workload/
  dummy_gpu.py         Python workload that calls libcudart via ctypes
  Dockerfile           Workload container image

docs/
  README.md            Entry point for documentation
  architecture.md      System diagram + component deep-dive
  deployment.md        Step-by-step deployment (demo + production)
  ai-context.md        This file — AI agent context
  ephemeral-debugging.md  kubectl debug walkthrough
```

---

## Key Design Decisions

### Why Go + cilium/ebpf instead of Python + BCC?

Linode Kubernetes Engine (LKE) does not provide kernel headers on worker nodes. BCC compiles BPF code at runtime and requires headers. `cilium/ebpf` with CO-RE compiles BPF at image build time and uses BTF to relocate types at load time — no headers needed at runtime.

### Why a mock agent?

The conference demo cluster has no physical NVIDIA GPUs. The mock agent (`agent/mock_agent/agent.py`) exposes **identical Prometheus metric names** as the real agent. This makes the Grafana dashboard and Prometheus config identical between demo and production environments.

### Namespace: `gpu-observability`

All resources are in the `gpu-observability` namespace to allow easy teardown (`kubectl delete namespace gpu-observability`).

---

## Prometheus Metrics Reference

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `gpu_cuda_allocated_bytes` | Gauge | `pid`, `workload` | Cumulative VRAM allocated via `cudaMalloc` |
| `gpu_cuda_kernel_launches_total` | Counter | `pid`, `workload` | Total `cudaLaunchKernel` calls |
| `gpu_kernel_duration_seconds` | Histogram | `workload` | Kernel execution latency |
| `gpu_utilization_percent` | Gauge | `gpu_id` | GPU compute utilisation (0-100) |
| `gpu_memory_used_bytes` | Gauge | `gpu_id` | VRAM currently in use |
| `gpu_memory_total_bytes` | Gauge | `gpu_id` | Total VRAM |
| `gpu_cuda_errors_total` | Counter | `error_code`, `workload` | CUDA API errors by type |

---

## Common Tasks for AI Agents

### Add a new eBPF probe (e.g. `cudaFree`)

1. Add a new BPF map and SEC program in `agent/bpf/tracer.c`
2. Run `make generate` from the `agent/` directory
3. In `agent/main.go`, attach the new uprobe via `exec.Uprobe(...)` and add a Prometheus metric
4. Rebuild Docker image and push

### Add a new Grafana panel

1. Edit the `grafana-dashboard-gpu` ConfigMap in `manifests/deploy-all.yaml` (the JSON key `gpu-observability.json`)
2. Add a new panel object to the `panels` array with the new PromQL query
3. Re-apply: `kubectl apply -f manifests/deploy-all.yaml`
4. Grafana auto-loads the dashboard within 10 seconds (provisioner polls every 10s)

### Change the Grafana admin password

In `manifests/deploy-all.yaml`, find:
```yaml
- name: GF_SECURITY_ADMIN_PASSWORD
  value: "kubecon2026"
```
Change the value and re-apply.

### Deploy to a different cluster

```bash
export KUBECONFIG=/path/to/new-kubeconfig.yaml
kubectl apply -f manifests/deploy-all.yaml
kubectl get svc grafana -n gpu-observability  # get new external IP
```

---

## Environment Variables

### `gpu-tracer` DaemonSet

| Variable | Default | Description |
|---|---|---|
| `LIBCUDART_PATH` | `/usr/local/cuda/lib64/libcudart.so` | Path to `libcudart.so` on the host (mounted via `hostPath /`) |

### Grafana (env in Deployment)

| Variable | Value | Description |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | `kubecon2026` | Admin password |
| `GF_AUTH_ANONYMOUS_ENABLED` | `true` | Allow public anonymous viewer |
| `GF_AUTH_ANONYMOUS_ORG_ROLE` | `Viewer` | Anonymous role |
| `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` | `/var/lib/grafana/dashboards/gpu-observability.json` | Auto-open dashboard on login |
