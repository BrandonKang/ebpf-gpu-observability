.PHONY: generate build push

IMAGE_NAME ?= ghcr.io/brandon/gpu-tracer
IMAGE_TAG ?= latest

generate:
	# Requires cilium/ebpf/cmd/bpf2go to be installed and clang
	go generate ./...

build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

push:
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
