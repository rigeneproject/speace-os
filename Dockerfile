FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    bison \
    flex \
    libelf-dev \
    libssl-dev \
    bc \
    kmod \
    cpio \
    gzip \
    xorriso \
    grub-pc-bin \
    grub-efi-amd64-bin \
    grub-efi-amd64-signed \
    shim-signed \
    mtools \
    dosfstools \
    e2fsprogs \
    parted \
    gdisk \
    squashfs-tools \
    fakeroot \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    python3-pydantic \
    python3-yaml \
    python3-structlog \
    python3-httpx \
    sudo \
    uidmap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY . /build

RUN echo "BUILD_USER=all" >> /etc/speace-build.conf

CMD ["/bin/bash", "/build/docker-build.sh"]