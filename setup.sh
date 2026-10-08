#!/bin/bash
# First-boot setup, run on the Nano as root: ./setup.sh
# Needs a network connection (plug in Ethernet).
set -euo pipefail

echo "== Set passwords"
passwd root
passwd alarm

echo "== Package keys + full update"
pacman-key --init
pacman-key --populate archlinuxarm
# Arch's stock kernel isn't booted (we use /boot/Image-nano); drop it so updates don't rebuild initramfs for nothing
pacman -Rns --noconfirm linux-aarch64 || true
pacman -Syu --noconfirm

echo "== Base packages"
pacman -S --needed --noconfirm sudo git vim htop python python-pip python-numpy zram-generator

echo "== sudo for the alarm user"
usermod -aG wheel alarm
echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
chmod 440 /etc/sudoers.d/wheel

echo "== Locale + time"
sed -i 's/^#en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
locale-gen
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
timedatectl set-ntp true   # no RTC battery, so the clock comes from the network

echo "== zram swap (4 GB RAM is tight for compiling)"
printf '[zram0]\nzram-size = ram / 2\n' > /etc/systemd/zram-generator.conf

echo "Done. Reboot, then ssh alarm@$(cat /etc/hostname) (or its IP)."
