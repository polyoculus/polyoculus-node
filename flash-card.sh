#!/bin/bash
# Flash Arch Linux ARM + the custom kernel onto a Jetson Nano SD card.
#   sudo ./flash-card.sh /dev/sdX nano-02
# Run ./build-kernel.sh first (as your normal user). ERASES the card's first partition.
set -euo pipefail
cd "$(dirname "$0")"
B=$PWD/build
DISK=${1:?usage: sudo $0 /dev/sdX <hostname>}
HOST=${2:?usage: sudo $0 /dev/sdX <hostname>}
MNT=$(mktemp -d)

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
[ -b "$DISK" ] && [ "$(lsblk -dno TYPE "$DISK")" = disk ] || { echo "$DISK is not a disk"; exit 1; }
[ "$(lsblk -dno RM "$DISK")" = 1 ] || { echo "$DISK is not removable, refusing"; exit 1; }
[ -f "$B/out/Image-nano" ] || { echo "no kernel in build/out, run ./build-kernel.sh first"; exit 1; }
KREL=$(ls "$B/out/lib/modules")

lsblk -o NAME,SIZE,FSTYPE,LABEL,MODEL "$DISK"
read -rp "Erase $DISK and install Arch as '$HOST'? Type yes: " ok
[ "$ok" = yes ] || exit 1
umount "$DISK"?* 2>/dev/null || true

# Old JetPack cards: keep NVIDIA's partition layout and reuse partition 1 (that's what's tested).
# Blank cards: one GPT partition for the whole card.
if ! lsblk -no NAME "$DISK" | sed -n 2p | grep -q .; then
    echo "label: gpt" | sfdisk "$DISK"
    echo ",,L" | sfdisk --append "$DISK"
    partprobe "$DISK"; sleep 2
fi
PART=$(lsblk -lnpo NAME "$DISK" | sed -n 2p)

# L4T's 2020-era U-Boot can't read these newer ext4 features
mkfs.ext4 -F -L APP -O ^metadata_csum_seed,^orphan_file "$PART"
PARTUUID=$(lsblk -no PARTUUID "$PART")
mount "$PART" "$MNT"
trap 'umount "$MNT" 2>/dev/null; rmdir "$MNT"' EXIT

echo "Extracting Arch Linux ARM..."
bsdtar -xpf "$B/ArchLinuxARM-aarch64-latest.tar.gz" -C "$MNT"

install -Dm644 "$B/out/Image-nano" "$MNT/boot/Image-nano"
install -Dm644 "$B/out/tegra210-p3450-0000.dtb" "$MNT/boot/dtbs-nano/tegra210-p3450-0000.dtb"
cp -a "$B/out/lib/modules/$KREL" "$MNT/usr/lib/modules/"
chown -R root:root "$MNT/usr/lib/modules/$KREL"

# video=...e forces HDMI on: the monitor's hotplug signal drops during modeset and never comes back
mkdir -p "$MNT/boot/extlinux"
cat > "$MNT/boot/extlinux/extlinux.conf" <<EOF
TIMEOUT 30
DEFAULT nano

LABEL nano
    MENU LABEL Arch Linux ARM ($KREL)
    LINUX /boot/Image-nano
    FDT /boot/dtbs-nano/tegra210-p3450-0000.dtb
    APPEND root=PARTUUID=$PARTUUID rw rootwait quiet video=HDMI-A-1:1920x1080@60e console=ttyS0,115200n8 console=tty0
EOF

echo "$HOST" > "$MNT/etc/hostname"
ln -sf /usr/share/zoneinfo/America/New_York "$MNT/etc/localtime"
install -m755 setup.sh "$MNT/root/setup.sh"

sync
echo "Done: $HOST on $DISK. Boot it, log in as root/root, run ./setup.sh"
