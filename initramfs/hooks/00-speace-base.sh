#!/bin/sh
# 00-speace-base.sh — hook mkinitcpio per SPEACE OS.
# In ambiente CI non usiamo mkinitcpio: l'initramfs è costruito a mano
# in iso/build.sh. Questo file resta come documentazione.

# Fasi mkinitcpio:
#   autodetect → modprobe → block → filesystems → keyboard → fsck → speace-base
#
# Aggiunge i moduli minimi per boot da CD/USB/HDD.

build() {
    add_module "cdrom"
    add_module "virtio_blk"
    add_module "virtio_pci"
    add_module "ahci"
    add_module "ata_piix"
    add_module "ext4"
    add_module "vfat"
    add_module "iso9660"
    add_binary "/usr/bin/mount"
    add_binary "/usr/bin/pivot_root"
    add_binary "/usr/bin/sleep"
    add_file "/init" "/init"
}

help() {
    cat <<HELPEOF
Questo hook aggiunge i moduli minimi per il boot di SPEACE OS.
HELPEOF
}
