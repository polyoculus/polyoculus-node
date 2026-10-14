# polyoculus-node

Everything that runs on a PolyOculus telescope node: one of the lab's original 2019 Jetson
Nanos (p3450, 4 GB), each driving one telescope's mount and guide camera. Covers the OS
(mainline 7.1 kernel + Arch Linux ARM, replacing NVIDIA's end-of-life Ubuntu 18.04),
fleet configuration, and the lab's node software.

```
os/build-kernel.sh   get the Nano kernel: download the published build, or compile it (~30 min)
os/flash-card.sh     write Arch + the kernel to an SD card
os/firstboot.sh      runs on the Nano's first boot: package keys, then ansible/site.yml locally
os/kernel/config     kernel config (Arch's, with the Nano's drivers built in)
ansible/             everything after first boot: packages, time sync, INDI, node software
mount/               iOptron CEM70 control over INDI (was pyMountOperator)
camera/              DMK 33UX273 guide camera + piezo steering mirror (was dmk-camera)
guide/               autoguiding: camera centroid -> mount guide pulses (+ an INDI-simulator test)
```

`mount/` and `camera/` were separate repos; they were imported with their full history.

## The rules

**The card is the node.** The Nanos are identical boards: a card's hostname is what makes it
nano-03, and any card works in any Nano. So there is no per-node
configuration anywhere; everything in `ansible/` is the same for every card.

**Nothing lives only on the SD card.** SD cards die. Every Nano must be rebuildable from this
repo in ~15 minutes, so calibration files and observation data have a copy off the card. Keep a
pre-flashed spare card at the observatory.

**No passwords.** Nodes outlive the people who set them up, so there is nothing to remember or
hand over: `alarm` logs in at the console with no password, root is locked, sudo asks for
nothing, and remote access is by identity (see "Access").

## New Nano, or replacing a dead card

On an x86_64 Linux machine:

```sh
cd os
./build-kernel.sh                         # downloads the published kernel, or compiles if there is none
sudo ./flash-card.sh /dev/sdX nano-03     # check the device with lsblk first!
```

`flash-card.sh` copies this repo, uncommitted changes included, to `/home/alarm/polyoculus-node`
on the card.

Put the card in the Nano, plug in Ethernet (and HDMI to watch), and power on. That's it: on first
boot `nano-firstboot.service` waits for the network and clock, sets up pacman, installs Ansible
and applies `site.yml` to itself, then reboots (~15 min). It retries every minute until it
succeeds; the login screen says whether it is running, failed or done, and the full log is
`/var/log/nano-firstboot.log`. Then log in as `alarm` (no password).

Later changes go out from your laptop (Ansible runs through `uvx`; you also need `rsync`,
which pushes this checkout to the Nanos as `~/polyoculus-node`, and your SSH key in
`ansible/files/authorized_keys/`):

```sh
cd ansible   # from the repo root
uvx --from ansible ansible-playbook site.yml --limit nano-03
```

Ansible reaches Nanos as `<name>.local`; if mDNS can't reach one, give it `ansible_host: <ip>`
in `inventory.yml`.
Rerunning `site.yml` is always safe; it only changes what differs. Note that deleting a line
from the config does not undo it on the Nanos: write `state: absent` instead.

## Access

There are no passwords; access is by SSH key, so handing the fleet to someone new never involves
a secret.

- **SSH keys** in `ansible/files/authorized_keys/<name>.pub`. Adding a person = commit their
  public key and run `site.yml`; removing = delete their file and run it again (the Nanos get
  exactly the keys in that folder).
- **Names:** every Nano answers to `<name>.local` on the lab network (mDNS), e.g.
  `ssh alarm@nano-03.local`, and that's how Ansible finds them (`inventory.yml`). Your laptop
  needs mDNS (macOS: built in; Linux: systemd-resolved with mDNS on, or avahi + nss-mdns).
- **Console:** keyboard + HDMI, log in as `alarm`, no password.

### Tailscale (off)

The group decided against Tailscale for now (`tailscale_enabled: false` in
`group_vars/nanos.yml`; turning it off also removes it from Nanos that had it). Remote access from
off the lab network needs a replacement when that comes up. If it's ever turned back on, the
role joins with `--ssh --advertise-tags=tag:nano`, and the tailnet (owned by a **lab** account,
not a student's) needs:

1. Access controls (policy file):
   ```json
   "tagOwners": { "tag:nano": ["autogroup:admin"] },
   "grants": [
     { "src": ["autogroup:member"], "dst": ["tag:nano"], "ip": ["*"] },
     { "src": ["tag:nano"], "dst": ["tag:nano"], "ip": ["*"] }
   ],
   "ssh": [
     { "action": "accept", "src": ["autogroup:member"], "dst": ["tag:nano"], "users": ["alarm"] }
   ]
   ```
2. Settings -> Keys -> auth key: **reusable, pre-approved, tags: tag:nano**.
3. `sudo TS_AUTHKEY=tskey-... os/flash-card.sh ...` for new cards, or
   `TS_AUTHKEY=tskey-... uvx --from ansible ansible-playbook site.yml` for running ones.

## Working on all Nanos at once

Ansible runs on all 8 in parallel (`forks = 8`). From `ansible/`:

```sh
uvx --from ansible ansible nanos -m ping                       # who's up
uvx --from ansible ansible nanos -a "uptime"                   # any command, everywhere
uvx --from ansible ansible nanos -b -a "systemctl restart indiserver"
```

For interactive work, tmux with one pane per Nano and `:setw synchronize-panes on` types into
all of them at once. Clocks: chrony on every Nano follows the internet pool and the other Nanos;
with no internet they elect one Nano and agree with it (`chronyc sources` shows who).

## Hardware on a node

- **Mount** (iOptron CEM70) and **fast steering mirror** controller are USB-serial. They get
  stable names `/dev/mount` and `/dev/fsm` from the USB port they're in, the same on every Nano:
  plug each into its labeled port once, run `udevadm info -q property /dev/ttyUSB0 | grep ^ID_PATH=`,
  and put the value in `usb_ports` in `ansible/group_vars/nanos.yml`. `guide.py` and `fsm.py`
  use these names when they exist.
- **Guide camera** (DMK 33UX273): found by name, any USB3 port.
- **indiserver** with the iOptron driver runs at boot on port 7624, so the mount can be driven
  over the network. INDI has no authentication: keep Nanos on the lab network. Stop it
  (`sudo systemctl stop indiserver`) before `guide.py simulate`, which needs the port.
- The node software lives in `~/polyoculus-node` with its Python environments already built
  (`uv run guide.py ...` in `guide/`, `.venv/bin/python dmk.py ...` in `camera/`). Ansible
  pushes your checkout there; captures/ on the Nano are never touched.
- A hung Nano reboots itself (hardware watchdog, 30 s).

## Updating

Arch updates continuously, so never update Nanos one by one by hand or they drift apart.

```sh
uvx --from ansible ansible-playbook upgrade.yml --limit nano-01   # canary first
# guide with nano-01 for a night, then everyone:
uvx --from ansible ansible-playbook upgrade.yml
```

The kernel is not a pacman package; see "Updating the kernel" below.

## Why a custom kernel

Arch's stock `linux-aarch64` kernel and initramfs don't boot on the Nano as shipped:

- **SD card never powers on.** The SD card's power regulator sits on the PMIC, which is
  reached over I2C, and `I2C_TEGRA` is a module. Arch's stock initramfs (generated on their
  build server) doesn't contain it, so the kernel waits forever for the root device.
- **Initramfs too big for NVIDIA's U-Boot.** L4T U-Boot loads the initramfs at 0x83200000
  and the kernel at 0x84000000, so anything over 14 MiB gets overwritten. Arch's initramfs is ~15 MB.
- **No fan.** `PWM_TEGRA` isn't enabled, so `pwm-fan` and the GPU regulator never probe.

`os/kernel/config` is Arch's config with `I2C_TEGRA`, `TEGRA_HOST1X`, `DRM_TEGRA`,
`DRM_CLIENT_LIB` and `PWM_TEGRA` built in, plus the USB (`xusb.bin`) and VIC firmware
embedded via `EXTRA_FIRMWARE`. With that, the Nano boots with no initramfs at all.

## Other gotchas (all handled by the scripts)

- **ext4 features:** L4T U-Boot (2020.04) can't read `metadata_csum_seed` or `orphan_file`,
  so `mkfs.ext4` turns them off.
- **HDMI goes black after boot:** the monitor's hotplug signal drops during the first modeset
  and the kernel never sees it come back, so nothing gets drawn.
  `video=HDMI-A-1:1920x1080@60e` forces the output on.
- **Boot path:** the Nano's bootloader (U-Boot) lives in the module's QSPI flash. It reads
  `/boot/extlinux/extlinux.conf` from the SD card's first partition. Boards must have run
  JetPack 4.5+ at least once so that QSPI firmware is current.
- **SError panic during boot:** on boards that ran L4T R32.7.x (JetPack 4.6.x), the firmware locks
  the power controller (`tegra-pmc: access to PMC is restricted to TZ`), and one of HDMI audio,
  the audio DMA/bus or nouveau (the GPU) crashes the Nano with "Asynchronous SError Interrupt" as
  udev loads it. The kernel command line blocks all four (`module_blacklist=`); nodes don't use them.
- **No clock battery:** the clock is wrong until NTP syncs, so journal timestamps from early boot are bogus.

## Updating the kernel

`upgrade.yml` updates everything except the kernel. For a new kernel: bump `KVER` in
`os/build-kernel.sh`, run it (`make olddefconfig` carries the config forward), and copy
`os/build/out/Image-nano`, the dtb and `lib/modules/<version>` onto the card. Once it boots,
publish it with `./build-kernel.sh --publish` so nobody else has to compile it.

## Debugging a boot that won't come up

Ansible keeps logs in RAM to save the card (`journal_storage: volatile`), so set it to
`persistent` on a Nano you are debugging. A freshly flashed card keeps logs until Ansible runs.
Then mount the card on a laptop and read
`/var/log/journal/*/system.journal`. Without `journalctl`, `strings -n 8 system.journal | grep ^MESSAGE=` works.
If nothing gets logged, a 3.3 V USB-serial adapter on the debug UART shows U-Boot and kernel
output (`console=ttyS0,115200` is already set).
