package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/rlimit"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go -target amd64 bpf bpf/tracer.c -- -I/usr/include/bpf -I/usr/include

var (
	cudaAllocatedBytes = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "gpu_cuda_allocated_bytes",
			Help: "Total bytes allocated via cudaMalloc per PID",
		},
		[]string{"pid"},
	)
	cudaLaunchCounts = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "gpu_cuda_kernel_launches_total",
			Help: "Total cudaLaunchKernel calls per PID",
		},
		[]string{"pid"},
	)
)

func main() {
	if err := rlimit.RemoveMemlock(); err != nil {
		log.Fatalf("Failed to remove memlock: %v", err)
	}

	objs := bpfObjects{}
	if err := loadBpfObjects(&objs, nil); err != nil {
		log.Fatalf("Failed to load objects: %v", err)
	}
	defer objs.Close()

	libcudartPath := os.Getenv("LIBCUDART_PATH")
	if libcudartPath == "" {
		libcudartPath = "/usr/local/cuda/lib64/libcudart.so" // default typical location
	}

	exec, err := link.OpenExecutable(libcudartPath)
	if err != nil {
		log.Fatalf("Failed to open executable %s: %v", libcudartPath, err)
	}

	uMalloc, err := exec.Uprobe("cudaMalloc", objs.UprobeCudaMalloc, nil)
	if err != nil {
		log.Fatalf("Failed to attach uprobe cudaMalloc: %v", err)
	}
	defer uMalloc.Close()

	uLaunch, err := exec.Uprobe("cudaLaunchKernel", objs.UprobeCudaLaunchKernel, nil)
	if err != nil {
		log.Fatalf("Failed to attach uprobe cudaLaunchKernel: %v", err)
	}
	defer uLaunch.Close()

	log.Println("eBPF probes attached successfully. Starting prometheus exporter on :8000")
	go func() {
		http.Handle("/metrics", promhttp.Handler())
		log.Fatal(http.ListenAndServe(":8000", nil))
	}()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		var pid uint32
		var bytes uint64

		iterBytes := objs.CudaMallocBytes.Iterate()
		for iterBytes.Next(&pid, &bytes) {
			cudaAllocatedBytes.WithLabelValues(fmt.Sprint(pid)).Set(float64(bytes))
		}

		var count uint64
		iterCounts := objs.CudaLaunchCounts.Iterate()
		for iterCounts.Next(&pid, &count) {
			cudaLaunchCounts.WithLabelValues(fmt.Sprint(pid)).Set(float64(count))
		}
	}
}
