#!/bin/bash
# First boot, run on the Nano as root (needs Ethernet): ./setup.sh
# Does only what Ansible can't do for itself; everything else is ansible/site.yml.
set -euo pipefail

echo "== Set passwords"
passwd root
passwd alarm

echo "== Package keys, full update, what Ansible needs (python, sudo)"
pacman-key --init
pacman-key --populate archlinuxarm
pacman -Syu --noconfirm python sudo
usermod -aG wheel alarm
echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
chmod 440 /etc/sudoers.d/wheel

echo "Done. From your laptop: cd ansible && ansible-playbook site.yml -K --limit $(cat /etc/hostname)"
