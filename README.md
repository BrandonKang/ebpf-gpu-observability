# eBPF GPU Observability

> **KubeCon Europe 2026** · *Hacking GPU Observability: eBPF & Ephemeral Containers in Action on Kubernetes*  
> Brandon Kang, Akamai Technologies · Wednesday March 25, 2026 · Hall 8 | Room F

Real-time GPU telemetry for Kubernetes AI/ML workloads using **eBPF uprobes** and **Kubernetes Ephemeral Containers** — zero code changes, zero disruption to production.

[![Grafana Dashboard](https://img.shields.io/badge/Grafana-Live%20Dashboard-orange?logo=grafana)](http://172.236.197.220/d/ebpf-gpu-obs/ebpf-gpu-observability)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.31-blue?logo=kubernetes)](https://kubernetes.io)
[![eBPF](https://img.shields.io/badge/eBPF-CO--RE-yellow)](https://ebpf.io)

---

## 🚀 Quick Start (Demo)

```bash
# Deploy full stack (namespace, Prometheus, Grafana, eBPF agent DaemonSet)
kubectl apply -f manifests/deploy-all.yaml --kubeconfig=<your-kubeconfig>

# Get public Grafana URL
kubectl get svc grafana -n gpu-observability
# Open http://<EXTERNAL-IP> in your browser
```

**Live demo dashboard (Deprecated) :** [http://172.236.197.220/d/ebpf-gpu-obs](http://172.236.197.220/d/ebpf-gpu-obs/ebpf-gpu-observability)

### 🎬 Demo Video

[Watch the eBPF GPU Observability demo](./assets/ebpf_demo.mov)
---

## 📚 Documentation

| Document | Description |
|---|---|
| [docs/README.md](./docs/README.md) | Project overview and quick-start |
| [docs/architecture.md](./docs/architecture.md) | System diagram, data flow, component details |
| [docs/deployment.md](./docs/deployment.md) | Step-by-step deployment guide (demo + production) |
| [docs/ephemeral-debugging.md](./docs/ephemeral-debugging.md) | `kubectl debug` walkthrough |
| [docs/ai-context.md](./docs/ai-context.md) | AI agent instructions and codebase map |

---

## 🧩 How It Works

```
cudaMalloc() in GPU workload
  │
  ▼  eBPF uprobe (kernel space, zero overhead)
BPF hash map → Go userspace poller
  │
  ▼  Prometheus metrics :8000/metrics
Prometheus (5s scrape) → Grafana (LoadBalancer, public)
```

The agent uses **cilium/ebpf with CO-RE** — compiles once, runs everywhere without kernel headers. Compatible with Linode Kubernetes Engine (LKE).

---

## 📁 Structure

```
agent/mock_agent/   Python mock agent (for demo without GPU hardware)
agent/              Real Go/eBPF agent (CO-RE, production-ready)
manifests/          Kubernetes YAML (deploy-all.yaml for one-command deploy)
workload/           Dummy GPU workload for testing
docs/               Documentation
```

---

## 🔐 Credentials

| Service | URL | Credentials |
|---|---|---|
| Grafana | `http://<EXTERNAL-IP>` | `admin` / `kubecon2026` (anonymous viewer enabled) |
| Prometheus | internal only (`prometheus:9090`) | — |
