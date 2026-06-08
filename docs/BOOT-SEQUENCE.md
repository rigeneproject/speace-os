# Boot Sequence — dal BIOS al cervello

Una descrizione step-by-step di cosa succede dal momento in cui accendi
la macchina (o avvii la ISO in QEMU) fino a quando l'organismo SPEACE è
completamente operativo.

## Fase 0: Firmware

- **BIOS**: carica MBR, esegue GRUB
- **UEFI**: legue EFI partition, esegue `grubx64.efi`

## Fase 1: GRUB

GRUB legge `boot/grub/grub.cfg` dall'ISO. Mostra menu:

```
SPEACE OS — Cognitive Operating System
SPEACE OS (safe mode — no AI coordinator)
SPEACE OS (verbose boot)
```

Default: prima voce, timeout 3 secondi.

GRUB carica in memoria:
- `/boot/bzImage` (kernel Linux 6.6.x)
- `/boot/initramfs.cpio.gz` (initramfs)

## Fase 2: Kernel

Il kernel:
1. Decomprime se stesso
2. Decomprime initramfs in RAMFS
3. Esegui `/init` come PID 1 transitorio
4. Console output: `SPEACE OS — Cognitive Operating System` (patch banner)

## Fase 3: Initramfs `/init`

```sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev
mount -t tmpfs none /run
mount -t tmpfs none /tmp

# Cerca rootfs
ROOT_DEVICE="/dev/sr0"  # ISO
[ ! -b "$ROOT_DEVICE" ] && ROOT_DEVICE="/dev/vda"  # QCOW2
[ ! -b "$ROOT_DEVICE" ] && ROOT_DEVICE="/dev/sda"  # disco

# Aspetta il device
for i in 1 2 3 4 5; do
    [ -b "$ROOT_DEVICE" ] && break
    sleep 1
done

# Monta e fai pivot
mkdir -p /newroot
mount -o ro "$ROOT_DEVICE" /newroot
cd /newroot
mkdir -p oldroot
pivot_root . oldroot
umount /oldroot/proc /oldroot/sys /oldroot/dev 2>/dev/null

# Esegui il vero PID 1
exec /sbin/os_coordinator
```

## Fase 4: os_coordinator (PID 1 finale)

`os_coordinator` parte come PID 1 del sistema. Stato iniziale: `BOOT`.

### 4.1 — BOOT

- Log `os-release`
- Mount (no-op se in dry-run)
- Crea `/var/log/speace`, `/var/lib/speace`, `/var/run/speace`
- Transizione → `IGNITION`

### 4.2 — IGNITION

- Carica `/etc/speace/coordinator.yaml`
- Carica env da `/etc/speace/env.conf`
- Verifica esistenza di `/etc/speace/services/<name>/`
- Marca tutti i servizi come `STOPPED` (verranno avviati dopo)
- Transizione → `COGNITION`

### 4.3 — COGNITION

- Chiede all'AI: "come strutturare l'avvio?"
- L'AI risponde in JSON:
  ```json
  {
    "phase_decision": "START_SERVICES",
    "actions": [
      {"service": "speace-brain", "op": "start"},
      {"service": "speace-evolution", "op": "start"},
      {"service": "speace-agi-team", "op": "start"},
      {"service": "speace-dashboard", "op": "start"}
    ],
    "reasoning": "avvio normale, tutti i moduli pronti",
    "urgency": "low"
  }
  ```
- Coordinator filtra le azioni tramite `policy.py`
- Per ogni azione accettata: scrive marker in `/var/run/speace/<service>.<op>`
- Il supervisore legge i marker e avvia i servizi
- Transizione → `IDLE`

### 4.4 — IDLE

- Ogni `heartbeat_interval_sec` (5s): aggiorna heartbeat di tutti i RUNNING
- Ogni `ai_consult_every_n_ticks` (default 6): consulta l'AI
- Se la salute degrada (servizi FAILED, metriche vitali basse) → `INTERVENTION`
- Se l'AI chiede SHUTDOWN → `SHUTDOWN`

### 4.5 — INTERVENTION (opzionale)

- Esegue le azioni richieste dall'AI
- Torna in `IDLE`

### 4.6 — SHUTDOWN

- Stop `speace-evolution` (flush proposte)
- Stop `speace-agi-team` (flush conversazioni)
- Stop `speace-dashboard`
- Stop `speace-brain` (salva snapshot)
- Stop supervisor
- `os_coordinator` esce → kernel panic o spegnimento (gestito da systemd-shutdown non presente)

## Output tipico di boot (console)

```
[    0.000000] SPEACE OS — Cognitive Operating System
[    0.000000] Linux version 6.6.46-speace-os
...
==================================================
 SPEACE OS — initramfs init
 2026-06-08 12:00:00
==================================================
[init] rootfs candidate: /dev/sr0
[init] montato /dev/sr0 in /newroot
[init] consegno il controllo a /sbin/os_coordinator
==================================================
 SPEACE OS — Cognitive Operating System
==================================================
[os_coordinator] OSCoordinator avviato in fase BOOT
[BOOT] NAME="SPEACE OS"
[BOOT] VERSION="0.1.0-cos (Alpine 3.20 base)"
[BOOT] ID=speace-os
[IGNITION] caricamento config e validazione installazione
[IGNITION] config caricata: 3 chiavi
[COGNITION] consulto l'agentic AI per il piano di avvio
[COGNITION] decisione AI: START_SERVICES (urgency=low)
[dispatch] speace-brain/start
[dispatch] speace-evolution/start
[dispatch] speace-agi-team/start
[dispatch] speace-dashboard/start
...
SPEACE OS 0.1.0-cos ttyS0

speace-os login: root
#
```

## Tempo tipico di boot

- BIOS → GRUB: 1-2s
- GRUB → kernel: <1s
- Kernel → initramfs: 1-2s
- Initramfs → rootfs: 2-3s (include mount + pivot)
- Rootfs → IDLE: 5-10s (include consulto AI)
- **Totale**: ~10-15 secondi
