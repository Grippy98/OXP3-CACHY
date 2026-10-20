FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates gcc make clang-19 lld-19 llvm-19 nasm xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
