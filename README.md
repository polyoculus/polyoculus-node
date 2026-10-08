# Arch Linux ARM on the Jetson Nano

Modern Arch Linux ARM (mainline kernel 7.1) on the original 2019 Jetson Nano dev kit
(p3450, 4 GB), replacing NVIDIA's end-of-life Ubuntu 18.04 / JetPack 4.6.

**No CUDA.** CUDA on the Nano only exists in NVIDIA's L4T kernel (JetPack 4.6, CUDA 10.2).
The mainline GPU driver (nouveau) gives OpenGL, not CUDA.

## Setting up a Nano

On an x86_64 Linux machine:

```sh
./build-kernel.sh                         # ~30 min the first time; skip if build/out exists
sudo ./flash-card.sh /dev/sdX nano-02     # check the device with lsblk first!
```

Put the card in the Nano, plug in HDMI, keyboard and Ethernet, boot, log in as `root` / `root`:

```sh
./setup.sh
```

That sets passwords, updates, installs sudo/python/git, and sets up locale, NTP and zram.
After that, `ssh alarm@<ip>`.

## Why a custom kernel

Arch's stock `linux-aarch64` kernel and initramfs don't boot on the Nano as shipped:

- **SD card never powers on.** The SD card's power regulator sits on the PMIC, which is
  reached over I2C, and `I2C_TEGRA` is a module. Arch's stock initramfs (generated on their
  build server) doesn't contain it, so the kernel waits forever for the root device.
- **Initramfs too big for NVIDIA's U-Boot.** L4T U-Boot loads the initramfs at 0x83200000
  and the kernel at 0x84000000, so anything over 14 MiB gets overwritten. Arch's initramfs is ~15 MB.
- **No fan.** `PWM_TEGRA` isn't enabled, so `pwm-fan` and the GPU regulator never probe.

`kernel/config` is Arch's config with `I2C_TEGRA`, `TEGRA_HOST1X`, `DRM_TEGRA`,
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

## Updating

`pacman -Syu` updates everything except the kernel. For a new kernel: bump `KVER` in
`build-kernel.sh`, run it (`make olddefconfig` carries the config forward), and copy
`build/out/Image-nano`, the dtb and `lib/modules/<version>` onto the card.

## Debugging a boot that won't come up

The system log persists on the card: mount it on a laptop and read
`/var/log/journal/*/system.journal`. Without `journalctl`, `strings -n 8 system.journal | grep ^MESSAGE=` works.
If nothing gets logged, a 3.3 V USB-serial adapter on the debug UART shows U-Boot and kernel
output (`console=ttyS0,115200` is already set).
