# Build locale di SPEACE OS

Questa guida spiega come buildare la distro localmente (Linux nativo o
in WSL su Windows).

## Requisiti

### Sistema operativo

- Linux x86_64 (Ubuntu 24.04, Debian 12, Fedora 39+, Arch)
- WSL2 su Windows 11
- ~10 GB di spazio disco
- ~2 GB di RAM per il build (la ISO finale è < 250 MB)

### Toolchain

```sh
# Debian/Ubuntu
sudo apt-get install -y \
    build-essential bc bison flex libelf-dev libssl-dev \
    curl wget cpio gzip rsync xorriso \
    grub-pc-bin grub-efi-amd64-bin grub-common \
    qemu-utils qemu-system-x86 mtools dosfstools

# Fedora
sudo dnf install -y \
    gcc make bc bison flex elfutils-libelf-devel openssl-devel \
    xorriso grub2-tools grub2-efi-x64-modules \
    qemu-img qemu-system-x86 mtools dosfstools rsync

# Arch
sudo pacman -S \
    base-devel bc bison flex libelf openssl \
    xorriso grub qemu-utils mtools dosfstools rsync
```

### Python

- Python 3.12+ (per i test del coordinatore)

## Build completa

```bash
cd SPEACE_OS_Cognitive_Operating_System
chmod +x iso/build.sh iso/pack-iso.sh iso/pack-qcow2.sh iso/pack-rootfs.sh kernel/build-kernel.sh

# Build completa (rootfs + kernel + initramfs + ISO)
sudo ./iso/build.sh

# Output
ls -la out/
```

Lo script `build.sh` produce:

```
out/
├── kernel/bzImage
├── initramfs.cpio.gz
├── rootfs/                    # rootfs pronto per chroot
├── rootfs.tar.gz
└── speace-os-0.1.0-cos.iso
```

## Build parziale

```bash
# Solo rootfs
./iso/pack-rootfs.sh

# Solo kernel
./kernel/build-kernel.sh 6.6.46

# Solo ISO (assume kernel e rootfs già in out/)
./iso/pack-iso.sh
```

## Test in QEMU

```bash
qemu-system-x86_64 \
    -m 3G \
    -smp 2 \
    -cdrom out/speace-os-0.1.0-cos.iso \
    -boot d \
    -serial mon:stdio
```

Output atteso:
```
[    0.000000] SPEACE OS — Cognitive Operating System
...
SPEACE OS 0.1.0-cos ttyS0

speace-os login: root (o speace)
```

## Test del coordinatore (Python only)

```bash
cd os_coordinator
pip install -e ".[dev]"
pytest tests/ -v
```

## Pulizia

```bash
./iso/cleanup.sh
```

## Troubleshooting

### "apk: command not found" durante la creazione del rootfs

Lo script usa Alpine `.tar.gz` pre-built, non richiede `apk` locale.

### "xorriso: command not found"

`xorriso` non è incluso in tutte le distro. Installalo o usa un'alternativa
(`genisoimage` per BIOS, `mkisofs` per fallback).

### "Permission denied" su /var/run/speace

Assicurati che la directory esista o che `os_coordinator` giri come root
con permessi di scrittura.

### Boot lento in QEMU senza KVM

Usa `-accel tcg` come fallback. KVM è molto più veloce su host Linux.

## Build per ARM64 (aarch64)

Non ancora supportato in 0.1.0-cos. Roadmap in CHANGELOG.
