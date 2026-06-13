#!/bin/sh
# test-initramfs-wiring.sh — verifica che il wiring initramfs → os_coordinator
# sia completo e consistente. Eseguibile in CI e in locale.
#
# Cosa controlla:
#   1. initramfs/sbin/os_coordinator esiste ed è eseguibile (su filesystem)
#   2. initramfs/init referenza /sbin/os_coordinator
#   3. iso/build.sh include il wrapper nell'initramfs e nel rootfs
#   4. (opzionale) se out/initramfs.cpio.gz esiste, verifica che contenga
#      il file sbin/os_coordinator con il bit eseguibile
#
# Exit code 0 = tutto ok, 1 = almeno un check fallito.

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
# qui/.. = iso/, qui/../.. = project root
ROOT="$(cd "${HERE}/../.." && pwd)"

PASS=0
FAIL=0
ok()   { echo "  [OK]   $*"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }

echo "=== Test wiring initramfs → os_coordinator ==="

# 1. Wrapper presente ed eseguibile
WRAPPER="${ROOT}/initramfs/sbin/os_coordinator"
if [ -f "${WRAPPER}" ]; then
    ok "wrapper presente: ${WRAPPER}"
    if [ -x "${WRAPPER}" ]; then
        ok "wrapper eseguibile (+x)"
    else
        fail "wrapper NON eseguibile (manca bit +x)"
    fi
    # Verifica shebang
    head1="$(head -n 1 "${WRAPPER}")"
    case "${head1}" in
        "#!/bin/sh"*|"#!/usr/bin/env sh"*) ok "shebang POSIX (${head1})" ;;
        *) fail "shebang non POSIX: ${head1}" ;;
    esac
    # Verifica che referenzi python3
    if grep -q "python3" "${WRAPPER}"; then
        ok "wrapper referenzia python3"
    else
        fail "wrapper non referenzia python3"
    fi
    # Verifica che esegua il modulo os_coordinator (non os_coordinatore!)
    if grep -qw "os_coordinator" "${WRAPPER}"; then
        ok "wrapper esegue -m os_coordinator"
    else
        fail "wrapper non esegue -m os_coordinator"
    fi
    # Verifica che NON usi il nome italiano (regressione)
    if grep -q "os_coordinatore" "${WRAPPER}"; then
        fail "wrapper usa 'os_coordinatore' (Italiano) invece di 'os_coordinator' (English)"
    else
        ok "wrapper non usa 'os_coordinatore' (regressione check)"
    fi
else
    fail "wrapper mancante: ${WRAPPER}"
fi

# 2. init referenza /sbin/os_coordinator
INIT="${ROOT}/initramfs/init"
if [ -f "${INIT}" ]; then
    if grep -q "/sbin/os_coordinator" "${INIT}"; then
        ok "init referenza /sbin/os_coordinator"
    else
        fail "init non referenzia /sbin/os_coordinator"
    fi
    if grep -q "/bin/sh" "${INIT}"; then
        ok "init ha fallback in /bin/sh (robust)"
    else
        fail "init non ha fallback in /bin/sh"
    fi
else
    fail "init mancante: ${INIT}"
fi

# 3. iso/build.sh installa il wrapper
BSH="${ROOT}/iso/build.sh"
if [ -f "${BSH}" ]; then
    if grep -q "sbin/os_coordinator" "${BSH}"; then
        ok "iso/build.sh referenzia sbin/os_coordinator"
    else
        fail "iso/build.sh non referenzia sbin/os_coordinator"
    fi
    if grep -q "chmod +x.*os_coordinator" "${BSH}"; then
        ok "iso/build.sh ha chmod +x sul wrapper"
    else
        fail "iso/build.sh non forza chmod +x sul wrapper"
    fi
else
    fail "iso/build.sh mancante: ${BSH}"
fi

# 4. Verifica contenuto del cpio.gz se esiste
CPIO="${ROOT}/out/initramfs.cpio.gz"
if [ -f "${CPIO}" ]; then
    # Estrai lista file dal cpio (gunzip | cpio -t)
    LIST=$(gunzip -c "${CPIO}" 2>/dev/null | cpio -t 2>/dev/null || true)
    if echo "${LIST}" | grep -q "sbin/os_coordinator"; then
        ok "initramfs.cpio.gz contiene sbin/os_coordinator"
    else
        fail "initramfs.cpio.gz NON contiene sbin/os_coordinator"
    fi
    if echo "${LIST}" | grep -q "^init$"; then
        ok "initramfs.cpio.gz contiene /init"
    else
        fail "initramfs.cpio.gz NON contiene /init"
    fi
    if echo "${LIST}" | grep -q "opt/os_coordinator"; then
        ok "initramfs.cpio.gz contiene opt/os_coordinator (modulo)"
    else
        fail "initramfs.cpio.gz NON contiene opt/os_coordinator"
    fi
else
    echo "  [SKIP] out/initramfs.cpio.gz non ancora generato (test opzionale)"
fi

# 5. pack-usb-img.sh presente, eseguibile, integro
USBIMG="${ROOT}/iso/pack-usb-img.sh"
if [ -f "${USBIMG}" ]; then
    ok "pack-usb-img.sh presente"
    if [ -x "${USBIMG}" ]; then
        ok "pack-usb-img.sh eseguibile (+x)"
    else
        fail "pack-usb-img.sh NON eseguibile (manca +x)"
    fi
    if grep -q "parted" "${USBIMG}"; then
        ok "pack-usb-img.sh usa parted (GPT)"
    else
        fail "pack-usb-img.sh non usa parted"
    fi
    if grep -q "EFI" "${USBIMG}"; then
        ok "pack-usb-img.sh prepara partizione EFI"
    else
        fail "pack-usb-img.sh non prepara EFI"
    fi
else
    fail "pack-usb-img.sh mancante: ${USBIMG}"
fi

# 6. Verifica .img se esiste
IMGFILE="${ROOT}/out/speace-os-$(cat "${ROOT}/VERSION" 2>/dev/null).img"
if [ -f "${IMGFILE}" ]; then
    SIZE=$(stat -c%s "${IMGFILE}" 2>/dev/null || stat -f%z "${IMGFILE}" 2>/dev/null)
    if [ "${SIZE}" -gt 104857600 ]; then  # > 100MB
        ok ".img size ok: $(echo "${SIZE}" | awk '{printf "%.1f MB", $1/1024/1024}')"
    else
        fail ".img troppo piccolo: ${SIZE} bytes"
    fi
    if head -c 8 "${IMGFILE}" | od -An -c | grep -q "EFI"; then
        ok ".img ha GPT signature (protective MBR)"
    else
        # GPT inizia con 'EFI PART' al sector 1
        if dd if="${IMGFILE}" bs=1 skip=512 count=8 2>/dev/null | grep -q "EFI PART"; then
            ok ".img ha GPT header (EFI PART)"
        else
            fail ".img non ha GPT valido (no protective MBR, no GPT header)"
        fi
    fi
else
    echo "  [SKIP] .img non ancora generato (test opzionale)"
fi

echo
echo "=== Risultato: ${PASS} pass, ${FAIL} fail ==="
if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
exit 0
