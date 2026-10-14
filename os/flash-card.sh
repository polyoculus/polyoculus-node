#!/bin/bash
# Flash Arch Linux ARM + the custom kernel onto a Jetson Nano SD card.
#   sudo ./flash-card.sh /dev/sdX nano-02
#   sudo TS_AUTHKEY=tskey-... ./flash-card.sh /dev/sdX nano-02   # also join Tailscale on first boot
# Run ./build-kernel.sh first (as your normal user). ERASES the card's first partition.
# The card sets itself up on first boot (firstboot.sh): it only needs Ethernet and power.
set -euo pipefail
cd "$(dirname "$0")"
REPO=$(cd .. && pwd)
B=$PWD/build
DISK=${1:?usage: sudo $0 /dev/sdX <hostname>}
HOST=${2:?usage: sudo $0 /dev/sdX <hostname>}
MNT=$(mktemp -d)

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
[ -b "$DISK" ] && [ "$(lsblk -dno TYPE "$DISK")" = disk ] || { echo "$DISK is not a disk"; exit 1; }
[ "$(lsblk -dno RM "$DISK")" = 1 ] || { echo "$DISK is not removable, refusing"; exit 1; }
[ -f "$B/out/Image-nano" ] || { echo "no kernel in build/out: run ./build-kernel.sh first"; exit 1; }
KREL=$(ls "$B/out/lib/modules")
grep -qE "^    $HOST:" "$REPO/ansible/inventory.yml" || { echo "$HOST is not in ansible/inventory.yml, add it first"; exit 1; }
[ -n "${TS_AUTHKEY:-}" ] || echo "No TS_AUTHKEY: $HOST joins Tailscale on a later 'TS_AUTHKEY=... ansible-playbook site.yml'."

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
# module_blacklist: one of these crashes the Nano (SError panic while udev loads drivers) on boards
# with L4T R32.7.x firmware, which locks the power controller (PMC). None is needed on a node.
mkdir -p "$MNT/boot/extlinux"
cat > "$MNT/boot/extlinux/extlinux.conf" <<EOF
TIMEOUT 30
DEFAULT nano

LABEL nano
    MENU LABEL Arch Linux ARM ($KREL)
    LINUX /boot/Image-nano
    FDT /boot/dtbs-nano/tegra210-p3450-0000.dtb
    APPEND root=PARTUUID=$PARTUUID rw rootwait quiet module_blacklist=snd_hda_tegra,tegra210_adma,tegra_aconnect,nouveau video=HDMI-A-1:1920x1080@60e console=ttyS0,115200n8 console=tty0
EOF

echo "$HOST" > "$MNT/etc/hostname"
# noatime goes here, not in rootflags=: ext4 rejects it there and the kernel panics.
# systemd remounts / with these options early in boot.
echo "PARTUUID=$PARTUUID / ext4 rw,noatime 0 0" >> "$MNT/etc/fstab"
ln -sf /usr/share/zoneinfo/UTC "$MNT/etc/localtime"
# No passwords: alarm logs in at the console with none (sshd refuses empty passwords, so remote
# access is only Tailscale SSH or the keys in ansible/files/authorized_keys); root is locked.
awk -F: -v OFS=: '$1 == "alarm" { $2 = "" } $1 == "root" { $2 = "!" } 1' "$MNT/etc/shadow" > "$MNT/etc/shadow.new"
cat "$MNT/etc/shadow.new" > "$MNT/etc/shadow" && rm "$MNT/etc/shadow.new"

# This repo, as it is on this laptop (uncommitted changes too), for first boot to run Ansible from
echo "Copying the repo..."
mkdir -p "$MNT/home/alarm/polyoculus-node"
{ git -c safe.directory='*' -C "$REPO" ls-files -coz --exclude-standard; printf '.git\0'; } \
    | tar -C "$REPO" --null -T - -cf - | tar -C "$MNT/home/alarm/polyoculus-node" -xf -
chown -R 1000:1000 "$MNT/home/alarm/polyoculus-node"   # alarm

install -m755 firstboot.sh "$MNT/usr/local/bin/nano-firstboot"
install -m644 nano-firstboot.service "$MNT/etc/systemd/system/nano-firstboot.service"
ln -sf /etc/systemd/system/nano-firstboot.service "$MNT/etc/systemd/system/multi-user.target.wants/nano-firstboot.service"
if [ -n "${TS_AUTHKEY:-}" ]; then
    (umask 077; echo "$TS_AUTHKEY" > "$MNT/root/ts-authkey")   # deleted once used
fi

sync
echo "Done: $HOST on $DISK. Put it in the Nano, plug in Ethernet (and HDMI to watch), power on."
echo "It sets itself up and reboots (~15 min). Then log in as alarm."
