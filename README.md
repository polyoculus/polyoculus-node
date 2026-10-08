# polyoculus-node

Everything that runs on a PolyOculus telescope node: one of the lab's original 2019 Jetson
Nanos (p3450, 4 GB), each driving one telescope's mount and guide camera. Covers the OS
(mainline 7.1 kernel + Arch Linux ARM, replacing NVIDIA's end-of-life Ubuntu 18.04),
fleet configuration, and the lab's node software.

```
os/build-kernel.sh   build the Nano kernel (x86_64 Linux, ~30 min the first time)
os/flash-card.sh     write Arch + the kernel to an SD card
os/setup.sh          first boot on the Nano: passwords, package keys, python for Ansible
os/kernel/config     kernel config (Arch's, with the Nano's drivers built in)
ansible/             everything after first boot: packages, time sync, Tailscale, INDI, SD-card wear
mount/               iOptron CEM70 control over INDI (was pyMountOperator)
camera/              DMK 33UX273 guide camera + piezo steering mirror (was dmk-camera)
guide/               autoguiding: camera centroid -> mount guide pulses (+ an INDI-simulator test)
```

`mount/` and `camera/` were separate repos; they were imported with their full history.

## The rule: nothing lives only on the SD card

SD cards die. Every Nano must be rebuildable from this repo in ~15 minutes, so anything unique
to one Nano (settings in `ansible/host_vars/`, calibration files, observation data) has a copy
off the card. Keep a pre-flashed spare card at the observatory.

## New Nano, or replacing a dead card

On an x86_64 Linux machine:

```sh
cd os
./build-kernel.sh                         # skip if build/out exists
sudo ./flash-card.sh /dev/sdX nano-03     # check the device with lsblk first!
```

Put the card in the Nano, plug in HDMI, keyboard and Ethernet, boot, log in as `root` / `root`:

```sh
./setup.sh
```

Then from your laptop (Ansible runs through `uvx`, nothing to install):

```sh
cd ansible   # from the repo root
TS_AUTHKEY=tskey-... uvx --from ansible ansible-playbook site.yml -K --limit nano-03
```

Until a Nano has joined Tailscale, give it `ansible_host: <ip>` in `inventory.yml`.
Rerunning `site.yml` is always safe; it only changes what differs. Note that deleting a line
from the config does not undo it on the Nanos: write `state: absent` instead.

## Updating

Arch updates continuously, so never update Nanos one by one by hand or they drift apart.

```sh
uvx --from ansible ansible-playbook upgrade.yml -K --limit nano-01   # canary first
# guide with nano-01 for a night, then everyone:
uvx --from ansible ansible-playbook upgrade.yml -K
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
- **No clock battery:** the clock is wrong until NTP syncs, so journal timestamps from early boot are bogus.

## Updating the kernel

`upgrade.yml` updates everything except the kernel. For a new kernel: bump `KVER` in
`os/build-kernel.sh`, run it (`make olddefconfig` carries the config forward), and copy
`os/build/out/Image-nano`, the dtb and `lib/modules/<version>` onto the card.

## Debugging a boot that won't come up

Ansible keeps logs in RAM to save the card (`journal_storage: volatile`), so set it to
`persistent` on a Nano you are debugging. A freshly flashed card keeps logs until Ansible runs.
Then mount the card on a laptop and read
`/var/log/journal/*/system.journal`. Without `journalctl`, `strings -n 8 system.journal | grep ^MESSAGE=` works.
If nothing gets logged, a 3.3 V USB-serial adapter on the debug UART shows U-Boot and kernel
output (`console=ttyS0,115200` is already set).
