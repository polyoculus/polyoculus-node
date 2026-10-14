#!/bin/bash
# Runs once on a freshly flashed Nano (nano-firstboot.service, installed by flash-card.sh).
# Does what setup.sh used to, then applies ansible/site.yml to this Nano from its own copy of
# the repo, so a new card needs nothing but Ethernet and power. Retries every minute until it
# succeeds; progress is on the HDMI console and in /var/log/nano-firstboot.log.
set -euo pipefail
exec > >(tee -a /var/log/nano-firstboot.log) 2>&1

HOST=$(cat /etc/hostname)
REPO=/home/alarm/polyoculus-node
step() { echo; echo "== nano-firstboot: $*"; }
issue() { printf '%s\n\n' "$1" > /etc/issue; }

issue "\\n: first-boot setup RUNNING, watch this screen or /var/log/nano-firstboot.log"
trap 'issue "\\n: first-boot setup FAILED, retrying every minute. See /var/log/nano-firstboot.log"' ERR

step "waiting for the network (plug in Ethernet)"
until curl -fsS -o /dev/null --max-time 5 http://mirror.archlinuxarm.org/; do sleep 5; done

# No clock battery: package signatures look like they come from the future until NTP syncs
step "waiting for NTP to set the clock"
for _ in $(seq 60); do
    [ "$(timedatectl show -p NTPSynchronized --value)" = yes ] && break
    sleep 5
done
date

step "package keys"
pacman-key --init
pacman-key --populate archlinuxarm

# We boot /boot/Image-nano; updating Arch's kernel would just rebuild an unused initramfs
if pacman -Q linux-aarch64 &>/dev/null; then pacman -Rdd --noconfirm linux-aarch64; fi

step "full update, plus what Ansible needs"
pacman -Syu --noconfirm --needed python sudo git ansible

step "ansible/site.yml for $HOST (local run)"
cd "$REPO/ansible"
[ -f /root/ts-authkey ] && TS_AUTHKEY=$(cat /root/ts-authkey) && export TS_AUTHKEY
ansible-playbook site.yml --connection local --limit "$HOST"
rm -f /root/ts-authkey

step "done"
systemctl disable nano-firstboot.service
rm -f /usr/local/bin/nano-firstboot
issue "\\n ($HOST): set up from polyoculus-node. Log in as alarm (no password)."
echo "Setup finished. Rebooting in 10 s (so noatime and the journal settings apply)."
sleep 10
systemctl reboot
