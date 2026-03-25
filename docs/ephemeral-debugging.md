# Ephemeral Container Debugging

Ephemeral containers let you inject a debug environment **directly into a running pod** without restarting it or modifying the production image. This is one of the core techniques demonstrated in the KubeCon talk.

---

## Why Ephemeral Containers?

Production images are deliberately minimal (distroless, scratch-based) — they have no shell, no `strace`, no debugging tools. Traditionally you had two bad choices:

1. Add debug tools to the production image (security risk, image bloat)
2. Restart the pod with a debug image sidecar (disrupts traffic)

Ephemeral containers solve both problems: they run in the same Pod, share the same PID namespace, network namespace, and volume mounts — and are completely **non-disruptive** to the main container.

---

## Prerequisites

```bash
# Kubernetes 1.23+ (ephemeral containers GA)
kubectl version --short

# Verify ephemeral containers work on your cluster
kubectl debug --help | grep "Running container"
```

---

## Basic Usage

### 1. Find the target pod

```bash
kubectl get pods -n gpu-observability -l app=dummy-gpu-workload
```

### 2. Inject a debug container

```bash
export POD=$(kubectl get pods -n gpu-observability -l app=dummy-gpu-workload \
              -o jsonpath='{.items[0].metadata.name}')

kubectl debug -it "$POD" \
  --image=ubuntu:22.04 \
  --target=dummy-gpu-workload \
  --namespace=gpu-observability \
  -- bash
```

- `--target` shares the process namespace with the named container
- `--image` is any debug image you want (ubuntu, busybox, custom tools)
- `-it` opens an interactive shell

### 3. Inside the ephemeral container

You now share the same Linux namespaces as the target container. PID 1 is the target process.

```bash
# Install debug tools on the fly (they won't persist after the container exits)
apt-get update && apt-get install -y strace procps iproute2

# Trace all syscalls of the main process
strace -p 1 -f -e trace=openat,read,write,ioctl 2>&1 | head -100

# List all processes sharing the pod's PID namespace
ps aux

# Inspect open file descriptors
ls -la /proc/1/fd

# Check network connections
ss -tulnp
```

---

## Tracing CUDA API Calls

If the target container is a GPU workload calling into `libcudart.so`, you can trace those calls from the ephemeral container:

```bash
# Trace all calls to cudaMalloc and cudaFree
strace -p 1 -f -e trace=brk,mmap,munmap -k 2>&1 | grep -i cuda

# Or using ltrace to trace library calls (if available)
apt-get install -y ltrace
ltrace -p 1 -e cudaMalloc+cudaFree+cudaLaunchKernel 2>&1
```

> **Note:** For deep CUDA API tracing, the real eBPF agent provides structured, low-overhead telemetry. Ephemeral containers are for ad-hoc, interactive debugging.

---

## Sharing Volumes for Log Inspection

If the target pod mounts a volume (e.g. a PVC for model checkpoints):

```bash
kubectl debug -it "$POD" \
  --image=ubuntu:22.04 \
  --target=dummy-gpu-workload \
  --namespace=gpu-observability \
  -- bash

# Inside, shared volumes are visible at the same paths as in the main container
ls /data/checkpoints
```

---

## Using a Custom Debug Image

Build a dedicated debug image with the tools you need:

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    strace ltrace gdb perf bpftrace linux-tools-generic \
    iproute2 tcpdump curl wget jq python3 \
    && rm -rf /var/lib/apt/lists/*
```

```bash
docker build -t ghcr.io/<org>/gpu-debug:latest .
docker push ghcr.io/<org>/gpu-debug:latest

kubectl debug -it "$POD" \
  --image=ghcr.io/<org>/gpu-debug:latest \
  --target=dummy-gpu-workload \
  -- bash
```

---

## Copy Mode (for CrashLoopBackOff Debugging)

When a pod keeps crashing, use `--copy-to` to clone the pod with a modified entrypoint:

```bash
kubectl debug "$POD" \
  --copy-to=debug-pod \
  --image=ubuntu:22.04 \
  --set-env="CRASH_ANALYSIS=1" \
  --namespace=gpu-observability \
  -- sleep infinity
```

This creates a new pod (`debug-pod`) with the same spec but overrides the command so you can inspect the container's filesystem without it crashing.

---

## Demo Script (KubeCon)

```bash
# 1. Show the running workload — no shell, no tools
kubectl exec -n gpu-observability "$POD" -- sh
# Error: OCI runtime exec failed: ... no such file or directory

# 2. Inject an ephemeral debug container
kubectl debug -it "$POD" \
  --image=ubuntu:22.04 \
  --target=dummy-gpu-workload \
  --namespace=gpu-observability \
  -- bash

# 3. Inside: show shared PID namespace
ps aux | head -5

# 4. Trace CUDA calls live
apt-get install -y strace -qq
strace -p 1 -f -e trace=ioctl -s 200 2>&1 | head -50

# 5. Exit — the ephemeral container vanishes, no trace left in the pod
exit

# 6. Verify the original pod is untouched
kubectl get pods -n gpu-observability
```
