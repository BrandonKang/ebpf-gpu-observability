import time
import ctypes
import os

print("Starting dummy GPU workload simulaton...", flush=True)

# Try to load libcudart to simulate CUDA presence
# If it fails, that's fine, we will just simulate a long-running process
# that an eBPF agent might try to trace anyway, or we provide instructions.
# For true simulation, we can just call some dummy exported functions if libcudart is present.

try:
    libcudart_path = os.getenv("LIBCUDART_PATH", "libcudart.so")
    libcudart = ctypes.CDLL(libcudart_path)
    has_cuda = True
    print(f"Loaded {libcudart_path}", flush=True)
except Exception as e:
    has_cuda = False
    print(f"Could not load libcudart: {e}. Running blind simulation loop.", flush=True)

# dummy pointers
dev_ptr = ctypes.c_void_p()

for i in range(1000000):
    if has_cuda:
        # Simulate cudaMalloc(void** devPtr, size_t size)
        # 1024 * 1024 = 1MB
        libcudart.cudaMalloc(ctypes.byref(dev_ptr), 1024 * 1024)
        time.sleep(0.5)
        # Simulate cudaFree(void* devPtr)
        libcudart.cudaFree(dev_ptr)
        
        # We can't easily simulate cudaLaunchKernel via ctypes easily due to complex args,
        # but the simple load loop is enough to generate uprobe hits if we were tracing cudaMalloc.
    else:
        # Just do nothing but stay alive
        pass
        
    time.sleep(1)
