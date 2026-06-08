# iso/ — build pipeline per la distro SPEACE OS

## Script

| File | Scopo |
|---|---|
| `build.sh` | build completa: kernel + rootfs + initramfs + ISO |
| `pack-iso.sh` | genera ISO avviabile con GRUB (BIOS+UEFI) |
| `pack-qcow2.sh` | genera immagine QCOW2 per KVM/QEMU |
| `pack-rootfs.sh` | impacchetta il rootfs come tar.gz |
| `cleanup.sh` | rimuove `out/` |

## Uso

```bash
# Build completa (root, perché scrive in /opt/speace ed esegue chroot)
sudo ./build.sh

# Solo rootfs
./pack-rootfs.sh

# Solo ISO (assume che kernel e rootfs siano già in out/)
./pack-iso.sh

# Pulizia
./cleanup.sh
```

## Output

Tutti gli artefatti finiscono in `../out/`:

```
out/
├── kernel/bzImage
├── initramfs.cpio.gz
├── rootfs/                    # directory rootfs (debug)
├── rootfs.tar.gz
├── speace-os-0.1.0-cos.iso    # ISO avviabile
├── speace-os-0.1.0-cos.qcow2  # disco per KVM
└── build.log
```

## Boot della ISO in QEMU

```bash
qemu-system-x86_64 -cdrom out/speace-os-0.1.0-cos.iso -m 2G -smp 2
```

## Requisiti di build

- Linux (x86_64)
- GCC, make, bc, bison, flex, libelf-dev, openssl-dev (per kernel)
- xorriso, grub-mkrescue, mtools (per ISO)
- qemu-utils (per qcow2)
- curl o wget (per scaricare Alpine e kernel)
- cpio, gzip (per initramfs)
- rsync (per copiare cellular_speace con filtri)
