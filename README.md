# GPU Observability Demo

This demo showcases how to use eBPF and ephemeral containers to monitor and debug GPU workloads on Kubernetes, specifically designed for Linode Kubernetes Engine (LKE) compatibility using BPF CO-RE (Compile Once - Run Everywhere).

## Structure
- `agent/`: The Go-based eBPF tracer that hooks into `libcudart.so` (`cudaMalloc`, `cudaLaunchKernel`) and exposes metrics via Prometheus.
- `manifests/`: Kubernetes YAML files to deploy the agent DaemonSet, Prometheus, Grafana, and the Grafana dashboard.
- `workload/`: A dummy Python workload that simulates CUDA library calls.

## Deployment

1. **Build and push the images** (Requires Docker and `go generate`):
   ```bash
   cd agent && make generate build push
   cd ../workload
   docker build -t ghcr.io/brandon/dummy-gpu:latest .
   docker push ghcr.io/brandon/dummy-gpu:latest
   ```

2. **Deploy to Kubernetes**:
   ```bash
   kubectl apply -f manifests/
   ```

3. **Access the Dashboard**:
   Wait for the Grafana LoadBalancer IP to be provisioned:
   ```bash
   kubectl get svc grafana
   ```
   Open `http://<EXTERNAL-IP>` in your browser to view the GPU Observability Dashboard.

## Ephemeral Containers Demo (Live Debugging)

To demonstrate live debugging without disrupting the running pod (as highlighted in the presentation), you can use Kubernetes Ephemeral Containers:

1. Find the dummy workload pod:
   ```bash
   export POD=$(kubectl get pods -l app=dummy-gpu-workload -o jsonpath='{.items[0].metadata.name}')
   ```
2. Inject an ephemeral debug container:
   ```bash
   kubectl debug -it $POD --image=ubuntu:22.04 --target=dummy-gpu-workload -- bash
   ```
3. Inside the ephemeral container, you share the process namespace with the target application. You can run tools like `strace`, `top`, or even attach lightweight BCC scripts locally if headers are present without installing them in the production image!
   ```bash
   apt-get update && apt-get install -y strace
   strace -p 1
   ```
# ebpf-gpu-observability
