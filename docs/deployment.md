# Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| `kubectl` | ≥ 1.28 | Cluster management |
| `docker` / `buildx` | ≥ 24 | Build container images |
| `go` | ≥ 1.21 | Build real eBPF agent |
| `clang` / `llvm` | ≥ 14 | Compile BPF C code |
| `libbpf-dev` | latest | BPF headers |

---

## Option A — Demo Deployment (Mock Agent, No GPU Required)

Use this for talks, demos, and CI environments where there's no physical GPU.

### 1. Connect to the cluster

```bash
export KUBECONFIG=/path/to/your-kubeconfig.yaml
kubectl get nodes  # verify connectivity
```

### 2. Deploy everything in one command

```bash
kubectl apply -f manifests/deploy-all.yaml
```

This creates the `gpu-observability` namespace and deploys:
- `prometheus` Deployment + ClusterRole + ServiceAccount
- `grafana` Deployment + LoadBalancer Service
- `gpu-tracer` DaemonSet (mock Python agent from `ttl.sh`)
- All provisioning ConfigMaps

### 3. Get the Grafana public URL

```bash
kubectl get svc grafana -n gpu-observability
# NAME      TYPE           CLUSTER-IP     EXTERNAL-IP        PORT(S)
# grafana   LoadBalancer   10.3.x.x       <your-public-ip>   80:...
```

Open `http://<EXTERNAL-IP>` in a browser.

> **Note:** LKE provisions a NodeBalancer automatically. It may take 30-60 seconds for the external IP to appear.

---

## Option B — Production Deployment (Real eBPF Agent)

Use this on clusters with NVIDIA GPUs and proper kernel BTF support.

### 1. Build the real eBPF agent

```bash
cd agent

# Install bpf2go tool
go install github.com/cilium/ebpf/cmd/bpf2go@latest

# Generate Go bindings from BPF C code (requires clang + libbpf)
make generate

# Build + push the Docker image
make build push IMAGE_NAME=ghcr.io/<your-org>/gpu-tracer IMAGE_TAG=latest
```

### 2. Update the DaemonSet image

Edit `manifests/agent-daemonset.yaml` and change:
```yaml
image: ttl.sh/ebpf-gpu-mock-agent:24h
```
to:
```yaml
image: ghcr.io/<your-org>/gpu-tracer:latest
```

### 3. Configure the CUDA library path

Set the `LIBCUDART_PATH` env var in the DaemonSet to match your node's library path:

```yaml
env:
- name: LIBCUDART_PATH
  value: /host/usr/local/cuda/lib64/libcudart.so
```

Common paths:
| Environment | Path |
|---|---|
| NVIDIA CUDA toolkit default | `/usr/local/cuda/lib64/libcudart.so` |
| Ubuntu / Debian system | `/usr/lib/x86_64-linux-gnu/libcudart.so` |
| Container-runtime host mount | `/host/usr/local/cuda/lib64/libcudart.so` |

### 4. Deploy

```bash
kubectl apply -f manifests/agent-daemonset.yaml \
              -f manifests/prometheus.yaml \
              -f manifests/grafana.yaml \
              -f manifests/dashboard.yaml
```

---

## Grafana Access

| URL | `http://<EXTERNAL-IP>/d/ebpf-gpu-obs/ebpf-gpu-observability` |
|---|---|
| Default dashboard | eBPF GPU Observability (auto-provisioned) |
| Anonymous access | ✅ Enabled (Viewer role) |
| Admin credentials | `admin` / `kubecon2026` |

Change the admin password in `manifests/deploy-all.yaml`:
```yaml
- name: GF_SECURITY_ADMIN_PASSWORD
  value: "your-secure-password"
```

---

## Teardown

```bash
kubectl delete namespace gpu-observability
kubectl delete clusterrole gpu-obs-prometheus
kubectl delete clusterrolebinding gpu-obs-prometheus
```

---

## Troubleshooting

### No data in Grafana

1. Check that Prometheus discovered the targets:
   ```bash
   kubectl run check --image=curlimages/curl:8.7.1 --restart=Never -n gpu-observability --rm -it \
     -- curl -s http://prometheus:9090/api/v1/targets | python3 -m json.tool | grep scrapeUrl
   ```

2. Check that the mock agent is running and exposing metrics:
   ```bash
   kubectl logs -n gpu-observability -l app=gpu-tracer --tail=20
   kubectl exec -n gpu-observability <gpu-tracer-pod> -- wget -qO- localhost:8000/metrics | head -20
   ```

### eBPF uprobe fails to attach (real agent)

- Verify BTF is enabled on nodes: `ls /sys/kernel/btf/vmlinux`
- Verify `libcudart.so` path: `kubectl exec <gpu-tracer-pod> -- ls /host/usr/local/cuda/lib64/`
- Check that CUDA driver is installed on the node (not just inside the container)

### LoadBalancer stuck in `<pending>`

LKE provisions NodeBalancers automatically — wait ~60s. If still pending:
```bash
kubectl describe svc grafana -n gpu-observability
```
Check for quota errors in the events.
