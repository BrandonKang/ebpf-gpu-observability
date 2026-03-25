# agent/Dockerfile

# Step 1: Build BPF Object using a clang environment
FROM ubuntu:22.04 AS bpf-builder
RUN apt-get update && apt-get install -y clang llvm libbpf-dev linux-libc-dev golang gcc
WORKDIR /app
# Pre-download dependencies
COPY go.mod go.sum ./
RUN go mod download || true

COPY . /app
# Run go generate to compile the BPF C code into Go files
RUN go generate ./...

# Step 2: Build the Go application
FROM golang:1.21-alpine AS go-builder
WORKDIR /app
COPY --from=bpf-builder /app /app
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o gpu-tracer .

# Step 3: Final lightweight runtime image
FROM alpine:3.18
WORKDIR /app
COPY --from=go-builder /app/gpu-tracer /app/
# We need to run as root/privileged for bpf, but we don't need compilation tools
CMD ["./gpu-tracer"]
