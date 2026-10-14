# How a node works

A PolyOculus node is one Jetson Nano (2019 dev kit, p3450 B01, 4 GB) driving one telescope:
an iOptron CEM70 mount over USB-serial, a DMK 33UX273 guide camera over USB3, and a piezo fast
steering mirror (FSM) controller over USB-serial. Everything on the Nano comes from this repo,
and every Nano is configured the same way; only its name differs.

## From blank card to running node

```
laptop                         SD card                              Nano, first boot
------                         -------                              ----------------
os/build-kernel.sh  -------->  /boot/Image-nano, dtb, modules
os/flash-card.sh    -------->  Arch Linux ARM rootfs
                               /boot/extlinux/extlinux.conf
                               /home/alarm/polyoculus-node (repo)
                               nano-firstboot.service  ----------->  wait for network + clock
                               polyoculus-identity.service           pacman keys, full update
                                                                     ansible-playbook site.yml
                                                                     (local run), reboot
laptop, later
-------------
ansible-playbook site.yml  ---- SSH to <name>.local ------------->  same playbook, pushes repo
```

1. **`os/build-kernel.sh`** downloads the prebuilt Nano kernel from this repo's GitHub releases
   (or compiles it). See [kernel.md](kernel.md) for why Arch's stock kernel can't be used.
2. **`os/flash-card.sh`** reformats the card's first partition, unpacks Arch Linux ARM, installs
   the kernel, writes the boot config, copies this repo onto the card, and installs two
   services. See [new-node.md](new-node.md).
3. **First boot** (`os/firstboot.sh`, run once by `nano-firstboot.service`): waits for internet
   and NTP, initializes pacman, installs Ansible, and applies `ansible/site.yml` to the Nano
   itself. It retries every minute until it succeeds, then disables itself and reboots.
4. **From then on**, changes go out from a laptop: `ansible-playbook site.yml` over SSH to every
   Nano at once. See [operations.md](operations.md).

## Boot chain

1. **U-Boot** in the Nano module's QSPI flash (installed by NVIDIA's JetPack; the board must have
   run JetPack 4.5+ once) reads `/boot/extlinux/extlinux.conf` from the card's first partition.
2. It loads **`/boot/Image-nano`** (mainline Linux 7.1, our build) and the device tree
   `tegra210-p3450-0000.dtb`. There is no initramfs: everything needed to reach the SD card is
   built into the kernel.
3. **systemd** starts. `polyoculus-identity.service` runs before networking and sets the
   hostname (below). Then networking (systemd-networkd, DHCP on Ethernet), name resolution and
   mDNS (systemd-resolved), time (chrony), SSH, and the node services.

## What runs on a node

| Service | What it does | Set up by |
|---|---|---|
| `polyoculus-identity` | names the Nano at every boot from `ansible/nodes.txt` | flash-card.sh, base role |
| `nano-firstboot` | first boot only: applies site.yml locally, then disables itself | flash-card.sh |
| `systemd-networkd` | DHCP on Ethernet (`en*`/`eth*`), mDNS on | Arch default + base role |
| `systemd-resolved` | DNS, and answers/resolves `<name>.local` (mDNS) | Arch default + base role |
| `chronyd` | time from the internet pool and from the other Nanos | base role |
| `sshd` | key-only SSH as `alarm` | Arch default + base role |
| `indiserver` | INDI server + iOptron driver on port 7624 | indi role |
| systemd watchdog | reboots a hung Nano (PMIC watchdog, 30 s) | hardware role |
| journald | logs in RAM only (`volatile`), to spare the card | sd-wear role |
| zram | compressed swap in RAM, no card writes | base role |

The node software (`camera/`, `mount/`, `guide/`) lives in `/home/alarm/polyoculus-node`, with
its Python environments already built by the software role. Nothing runs it automatically yet:
observing is started by hand (see [observing.md](observing.md)).

## Names

Cards are interchangeable, so a Nano's name comes from the hardware it's attached to, decided at
every boot by `os/identity.sh` from `ansible/nodes.txt`:

1. the node listing this Nano's **guide camera serial** (the camera stays with its telescope),
2. else the node listing one of this **board's MAC addresses**,
3. else the name the card was **flashed with** (`flash-card.sh /dev/sdX nano-03`),
4. else **`nano-<last 4 hex digits of the MAC>`**.

The login screen shows the camera serial and MAC, so pinning a telescope to a name is: read the
screen, add the serial to that node's line in `nodes.txt`, commit, and run site.yml (which
pushes the new table to every Nano). `nodes.txt` is also Ansible's inventory (`inventory.py`).

## Network, time, access

- **Finding Nanos:** every Nano answers to `<name>.local` over mDNS on the local network. No IP
  addresses are recorded anywhere. Tailscale support exists in the repo but is off (the group
  decided against it); see [operations.md](operations.md#access).
- **Time:** the Nano has no clock battery and boots with a wrong clock. chrony steps it as soon
  as it reaches a server. Every Nano lists the internet pool *and* every other Nano; with no
  internet, chrony's orphan mode elects one Nano and the rest follow it, so the fleet still
  agrees with itself (what synchronized observing needs).
- **Access:** no passwords. `alarm` logs in at the console with an empty password; SSH accepts
  only the keys in `ansible/files/authorized_keys/` (exactly those: deleting a key file revokes
  it); root is locked; sudo needs no password.

## Hardware names

- **`/dev/mount`, `/dev/fsm`:** udev symlinks for the two USB-serial adapters, chosen by which
  USB **port** they're plugged into (`usb_ports` in `ansible/group_vars/nanos.yml`), the same on
  every Nano. `guide.py` and `fsm.py` default to them when they exist.
- **Guide camera:** found by its name (`DMK 33UX273`) in any USB3 port; no rule needed.

## The SD card

SD cards are the weakest part. The setup limits writes (logs in RAM, `noatime`, zram swap) and
assumes any card can die: a Nano is rebuilt by flashing a new card (~2 min) and letting first
boot run (~15-20 min). So **nothing may live only on a card**: observation data and calibration
files have to be copied off ([operations.md](operations.md#getting-data-off-the-nanos)).
