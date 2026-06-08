# Changelog

Tutte le modifiche notevoli a SPEACE OS sono documentate qui.

Il formato è ispirato a [Keep a Changelog](https://keepachangelog.com/),
e il progetto aderisce a [Semantic Versioning](https://semver.org/).

## [0.1.0-cos] - 2026-06-08

### Aggiunto
- `os_coordinator/`: PID 1 cognitivo con state machine a 6 fasi (BOOT, IGNITION, COGNITION, IDLE, INTERVENTION, SHUTDOWN)
- `os_coordinator/agentic_brain.py`: wrapper Ollama Cloud per `minimax-m3:cloud` con system prompt dedicato al coordinatore
- `os_coordinator/policy.py`: filtro azioni (whitelist + rate limit su restart)
- `os_coordinator/health.py`: watchdog servizi + metriche vitali
- `os_coordinator/state_machine.py`: macchina a stati con history e snapshot
- 25 unit test del coordinatore (`os_coordinator/tests/`)
- `rootfs/`: overlay completo (etc/os-release, etc/speace/{coordinator.yaml, env.conf, services/}, etc/motd, etc/profile.d/speace.sh, usr/local/bin/{speace-os-init, speace-os-status}, lib/speace/supervisor.py)
- 4 servizi canonici: `speace-brain`, `speace-evolution`, `speace-agi-team`, `speace-dashboard` con script `run` eseguibili
- `supervisor.py`: service manager s6-like con auto-restart entro limiti, marker-based dispatch
- `kernel/`: linux-config minimale (no DRM, no wireless, no sound) + script `build-kernel.sh` per Linux 6.6 LTS
- `initramfs/init`: bootstrap minimo che monta rootfs e consegna il controllo a `os_coordinator`
- `iso/`: pipeline completa (`build.sh`, `pack-iso.sh`, `pack-qcow2.sh`, `pack-rootfs.sh`, `cleanup.sh`)
- CI GitHub Actions: `build-distro.yml` (matrice iso/qcow2/rootfs + smoke test), `test-os-coordinator.yml` (Python 3.12/3.13), `publish-release.yml`
- `docs/`: 6 documenti (ARCHITECTURE, BOOT-SEQUENCE, COORDINATOR, SERVICE-MANAGEMENT, BUILD, SECURITY-MODEL)

### Note
- Versione alpha, interna. Boot reale in QEMU ancora da verificare end-to-end.
- L'API key Ollama Cloud è hardcoded in `env.conf` con commento esplicito; da spostare in variabile d'ambiente in produzione.
- Nessun driver grafico: solo console seriale e tty0.
