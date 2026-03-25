#include <linux/bpf.h>
#include <linux/ptrace.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char __license[] SEC("license") = "Dual MIT/GPL";

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, __u64);
} cuda_malloc_bytes SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, __u64);
} cuda_launch_counts SEC(".maps");

// For a uprobe on: cudaError_t cudaMalloc(void** devPtr, size_t size)
// size is passed as the 2nd argument.
SEC("uprobe/cudaMalloc")
int uprobe_cudaMalloc(struct pt_regs *ctx) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    __u64 size = (__u64)PT_REGS_PARM2(ctx);

    __u64 *val = bpf_map_lookup_elem(&cuda_malloc_bytes, &pid);
    if (val) {
        __sync_fetch_and_add(val, size);
    } else {
        __u64 init_val = size;
        bpf_map_update_elem(&cuda_malloc_bytes, &pid, &init_val, BPF_ANY);
    }
    return 0;
}

// For a uprobe on: cudaError_t cudaLaunchKernel(const void* func, dim3 gridDim, dim3 blockDim, void** args, size_t sharedMem, cudaStream_t stream)
SEC("uprobe/cudaLaunchKernel")
int uprobe_cudaLaunchKernel(struct pt_regs *ctx) {
    __u32 pid = bpf_get_current_pid_tgid() >> 32;

    __u64 *val = bpf_map_lookup_elem(&cuda_launch_counts, &pid);
    if (val) {
        __sync_fetch_and_add(val, 1);
    } else {
        __u64 init_val = 1;
        bpf_map_update_elem(&cuda_launch_counts, &pid, &init_val, BPF_ANY);
    }
    return 0;
}
