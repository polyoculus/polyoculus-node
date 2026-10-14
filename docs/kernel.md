# The Nano kernel

Nodes run mainline Linux (7.1.x) built from `os/kernel/config`, not Arch Linux ARM's stock
`linux-aarch64` package, and boot it with no initramfs. Ansible removes the stock package so
pacman never touches the kernel.

## Why not Arch's kernel

Arch's stock kernel and initramfs don't boot on the Nano as shipped:

- **The SD card never powers on.** Its power regulator sits on the PMIC, reached over I2C, and
  `I2C_TEGRA` is a module. Arch's initramfs (generated on their build server) doesn't contain
  it, so the kernel waits forever for the root device.
- **The initramfs is too big for NVIDIA's U-Boot.** L4T U-Boot loads the initramfs at
  0x83200000 and the kernel at 0x84000000, so anything over 14 MiB gets overwritten; Arch's is ~15 MB.
- **No fan.** `PWM_TEGRA` isn't enabled, so `pwm-fan` and the GPU regulator never probe.

`os/kernel/config` is Arch's config with `I2C_TEGRA`, `TEGRA_HOST1X`, `DRM_TEGRA`,
`DRM_CLIENT_LIB` and `PWM_TEGRA` built in, and the USB controller (`xusb.bin`) and video engine
(VIC) firmware embedded with `EXTRA_FIRMWARE`. With that, nothing needed to reach the SD card is
a module, and no initramfs is needed.

## Getting it: `os/build-kernel.sh`

```sh
./build-kernel.sh            # download the published build if there is one, else compile
./build-kernel.sh --build    # always compile
./build-kernel.sh --publish  # upload build/out as a GitHub release (after it has booted!)
```

Output goes to `os/build/out/` (`Image-nano`, `tegra210-p3450-0000.dtb`,
`lib/modules/<version>-nano/`), which `flash-card.sh` installs. The script also downloads and
GPG-verifies the Arch Linux ARM tarball (the rootfs, and the source of the embedded firmware).

**Releases** are tagged `kernel-<KVER>-<first 12 hex of sha256(os/kernel/config)>`, e.g.
`kernel-7.1.6-5c3a3c54e502`, with `kernel-<KVER>-nano.tar.zst` and its `.sha256`. Because the
tag includes the config hash, changing the config can never pick up an old binary: the script
finds no matching release and compiles. Downloading needs `gh` logged in (the repo is private).

**Compiling** needs an x86_64 Linux machine with clang, lld, llvm, make, bc, flex, bison, perl,
pahole, openssl, libelf, bsdtar, curl, gpg (Arch:
`sudo pacman -S --needed clang lld llvm make bc flex bison perl pahole openssl libelf libarchive`).
It cross-compiles with `LLVM=1`; the first build takes 10-40 min depending on the machine, later
ones only rebuild what changed. Sources and objects stay in `os/build/linux-<KVER>/`
(git-ignored).

## Changing the config

```sh
cd os/build/linux-7.1.6
scripts/config --file ../../kernel/config -e SOME_OPTION      # -d to disable, -m for module
cd ../.. && ./build-kernel.sh
```

`make olddefconfig` (run by the script) fills in dependencies. Check the result in
`build/linux-*/.config`: an option whose dependencies aren't met is silently dropped. Then test
on one Nano before publishing.

Don't trim the config to speed up builds without a reason. It was tried (dropping other SoCs,
PC hardware and TV tuners cut modules by 45% and build time from 40 to 10 min) and reverted: the
fleet runs the full config, which is the one that has been tested on hardware.

## Updating to a new kernel version

1. Bump `KVER` in `build-kernel.sh` and run it (it downloads and checks the new source).
   `olddefconfig` carries `kernel/config` forward; review new options if the jump is large.
2. Test it on one Nano (below), observe with it for a night.
3. `./build-kernel.sh --publish`, commit the `KVER` (and any config) change.

## Installing a new kernel on running Nanos

Not automated yet (a candidate for an Ansible role). By hand, per Nano, from the repo root:

```sh
n=nano-03.local; out=os/build/out; v=$(ls $out/lib/modules)
rsync -a $out/Image-nano $out/tegra210-p3450-0000.dtb $out/lib/modules/$v alarm@$n:/tmp/
ssh alarm@$n "sudo install -m644 /tmp/Image-nano /boot/Image-nano &&
  sudo install -m644 /tmp/tegra210-p3450-0000.dtb /boot/dtbs-nano/ &&
  sudo rm -rf /usr/lib/modules/$v && sudo cp -a /tmp/$v /usr/lib/modules/ &&
  sudo chown -R root:root /usr/lib/modules/$v && sudo reboot"
```

If the new kernel doesn't boot, that Nano needs its card reflashed (or `Image-nano` copied back
on a laptop), so do one Nano first, and keep a spare flashed card at hand. New cards get the new
kernel automatically from `flash-card.sh`.

## Boot details and gotchas (handled by the scripts)

- **Boot path:** U-Boot in the module's QSPI flash reads `/boot/extlinux/extlinux.conf` from
  the card's first partition. Boards must have run JetPack 4.5+ once, so that firmware is
  current. flash-card.sh keeps NVIDIA's partition layout on old JetPack cards and reuses
  partition 1 (that's what has been tested).
- **ext4 features:** L4T U-Boot (2020.04) can't read `metadata_csum_seed` or `orphan_file`, so
  `mkfs.ext4` turns them off.
- **`noatime` goes in `/etc/fstab`, not `rootflags=`.** ext4 rejects `noatime` as a mount data
  option, so `rootflags=noatime` on the command line makes every filesystem refuse the root
  device and the kernel panics. systemd remounts `/` with the fstab options early in boot.
- **SError panic:** boards that ran JetPack 4.6 (L4T R32.7.x) lock the PMC (power controller)
  in the secure firmware (`tegra-pmc: access to PMC is restricted to TZ`). One of HDMI audio
  (`snd_hda_tegra`), the audio DMA/bus (`tegra210_adma`, `tegra_aconnect`) or the GPU
  (`nouveau`) then touches unpowered hardware as udev loads it, and the Nano dies with
  "Asynchronous SError Interrupt". The command line blocks all four with `module_blacklist=`;
  nodes don't use any of them. (Not narrowed down to one: not worth more boot cycles.)
- **HDMI goes black after boot:** the monitor's hotplug signal drops during the first modeset
  and the kernel never sees it come back. `video=HDMI-A-1:1920x1080@60e` forces the output on.
- **No clock battery:** the clock is wrong until NTP syncs, so early-boot log timestamps are bogus.

The kernel command line (in `flash-card.sh`):
`root=PARTUUID=... rw rootwait quiet module_blacklist=... video=HDMI-A-1:1920x1080@60e console=ttyS0,115200n8 console=tty0`.

## Jetson Orin (not supported yet)

The lab has two Orin Nano 8 GB dev kits (p3767-0005 module on p3768 carrier), set aside for now.
Checked in Oct 2026: mainline already has their device tree
(`tegra234-p3768-0000+p3767-0005.dtb`) and most drivers, and the Orin's UEFI firmware boots from
the same `extlinux.conf` format. Needed: `PCIE_TEGRA194_HOST` + `PHY_TEGRA194_P2U` (the
Ethernet is on PCIe) and `SERIAL_TEGRA_TCU` (console); USB needs no firmware file (the Orin's
bootloader loads it); flash-card.sh would need an Orin profile (dtb, console). Limitation:
mainline has **no Orin display driver** (NVIDIA moved display control to a separate processor
whose driver only exists in JetPack), so Orins would run headless.
