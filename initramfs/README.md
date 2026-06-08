# initramfs/ — initramfs minimale di SPEACE OS

Contiene solo:
- `init`: bootstrap minimo che monta rootfs ed esegue `os_coordinator` come PID 1 finale.
- `hooks/`: hook mkinitcpio (solo documentazione, in CI usiamo `cpio` diretto).

L'initramfs è costruito a mano in `iso/build.sh` con:
```sh
cd initramfs/
find . | cpio -o -H newc | gzip -9 > ../out/initramfs.cpio.gz
```

## init flow

1. Kernel esegue `/init` (questa initramfs)
2. `init` monta proc/sys/dev/run/tmp
3. `init` cerca il rootfs (`/dev/sr0`, `/dev/vda`, `/dev/sda`)
4. `init` esegue `pivot_root` e `chroot` nel rootfs
5. `init` esegue `exec /sbin/os_coordinator` → diventa il PID 1 finale
6. `os_coordinator` inizia il ciclo di vita: BOOT → IGNITION → COGNITION → IDLE
