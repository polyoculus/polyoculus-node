#!/bin/bash
# Build the Jetson Nano kernel (Tegra drivers built in, no initramfs needed).
# Runs as a normal user on an x86_64 Linux box. Needs: clang, lld, llvm, make, bc, flex, bison,
# perl, pahole, openssl and libelf headers, bsdtar, curl, gpg.
# Output: build/out/ (Image, dtb, modules) which flash-card.sh installs.
set -euo pipefail
cd "$(dirname "$0")"
KVER=7.1.6
ALARM_URL=http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz
ALARM_KEY=68B3537F39A313B3E574D06777193F152BDBE6A6
B=$PWD/build
mkdir -p "$B"

# Arch Linux ARM rootfs tarball (also the source of the Tegra firmware)
if [ ! -f "$B/ArchLinuxARM-aarch64-latest.tar.gz" ]; then
    curl -fL -o "$B/ArchLinuxARM-aarch64-latest.tar.gz" "$ALARM_URL"
    curl -fL -o "$B/ArchLinuxARM-aarch64-latest.tar.gz.sig" "$ALARM_URL.sig"
fi
export GNUPGHOME="$B/gnupg"; mkdir -p -m700 "$GNUPGHOME"
gpg -q --keyserver hkps://keyserver.ubuntu.com --recv-keys "$ALARM_KEY"
gpg --verify "$B/ArchLinuxARM-aarch64-latest.tar.gz.sig" "$B/ArchLinuxARM-aarch64-latest.tar.gz"

# Firmware that gets embedded into the kernel (USB controller, video engine)
mkdir -p "$B/fw"
bsdtar -xzf "$B/ArchLinuxARM-aarch64-latest.tar.gz" -C "$B/fw" --strip-components 4 './usr/lib/firmware/nvidia/tegra210/'

# Kernel source
if [ ! -d "$B/linux-$KVER" ]; then
    curl -fL -o "$B/linux-$KVER.tar.xz" "https://cdn.kernel.org/pub/linux/kernel/v${KVER%%.*}.x/linux-$KVER.tar.xz"
    (cd "$B" && curl -fsSL "https://cdn.kernel.org/pub/linux/kernel/v${KVER%%.*}.x/sha256sums.asc" \
        | grep " linux-$KVER.tar.xz$" | sha256sum -c -)
    tar -xf "$B/linux-$KVER.tar.xz" -C "$B"
fi

cd "$B/linux-$KVER"
cp ../../kernel/config .config
scripts/config --set-str EXTRA_FIRMWARE_DIR "$B/fw"
make ARCH=arm64 LLVM=1 olddefconfig
make ARCH=arm64 LLVM=1 -j"$(nproc)" Image modules dtbs

rm -rf "$B/out"
mkdir -p "$B/out"
make ARCH=arm64 LLVM=1 INSTALL_MOD_PATH="$B/out" INSTALL_MOD_STRIP=1 modules_install
rm -f "$B/out/lib/modules/"*/build
cp arch/arm64/boot/Image "$B/out/Image-nano"
cp arch/arm64/boot/dts/nvidia/tegra210-p3450-0000.dtb "$B/out/"
echo "Built $(make -s ARCH=arm64 LLVM=1 kernelrelease) into $B/out"
