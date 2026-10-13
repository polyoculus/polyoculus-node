#!/bin/bash
# Build the Jetson Nano kernel (Tegra drivers built in, no initramfs needed).
# Runs as a normal user on an x86_64 Linux box. Needs: clang, lld, llvm, make, bc, flex, bison,
# perl, pahole, openssl and libelf headers, bsdtar, curl, gpg.
# Output: build/out/ (Image, dtb, modules) which flash-card.sh installs.
#
# If this kernel version and config were already built and published as a GitHub release, it
# downloads that instead (needs the gh CLI, logged in: the repo is private). --build always compiles.
# Publish a build once it has booted on a Nano: ./build-kernel.sh --publish
set -euo pipefail
cd "$(dirname "$0")"
KVER=7.1.6
ALARM_URL=http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz
ALARM_KEY=68B3537F39A313B3E574D06777193F152BDBE6A6
B=$PWD/build
mkdir -p "$B"
# The release is named after the kernel version and a hash of the config, so editing the config
# never picks up an old binary
TAG=kernel-$KVER-$(sha256sum kernel/config | cut -c1-12)
PKG=kernel-$KVER-nano.tar.zst
GH_REPO=polyoculus/polyoculus-node

if [ "${1:-}" = --publish ]; then
    [ -f "$B/out/Image-nano" ] || { echo "nothing in build/out to publish"; exit 1; }
    tar -C "$B/out" -I 'zstd -19 -T0' -cf "$B/$PKG" .
    (cd "$B" && sha256sum "$PKG" > "$PKG.sha256")
    gh release create "$TAG" "$B/$PKG" "$B/$PKG.sha256" -R "$GH_REPO" --target master \
        --title "Nano kernel $KVER ($TAG)" \
        --notes "Built by os/build-kernel.sh from os/kernel/config (sha256 ${TAG##*-}...). build-kernel.sh downloads this instead of compiling."
    exit 0
fi

# Arch Linux ARM rootfs tarball (also the source of the Tegra firmware)
if [ ! -f "$B/ArchLinuxARM-aarch64-latest.tar.gz" ]; then
    curl -fL -o "$B/ArchLinuxARM-aarch64-latest.tar.gz" "$ALARM_URL"
    curl -fL -o "$B/ArchLinuxARM-aarch64-latest.tar.gz.sig" "$ALARM_URL.sig"
fi
export GNUPGHOME="$B/gnupg"; mkdir -p -m700 "$GNUPGHOME"
gpg -q --keyserver hkps://keyserver.ubuntu.com --recv-keys "$ALARM_KEY"
gpg --verify "$B/ArchLinuxARM-aarch64-latest.tar.gz.sig" "$B/ArchLinuxARM-aarch64-latest.tar.gz"

# Prebuilt kernel for exactly this version and config, if one was published
if [ "${1:-}" != --build ] && command -v gh >/dev/null &&
    gh release download "$TAG" -R "$GH_REPO" -D "$B" --clobber -p "$PKG" -p "$PKG.sha256" 2>/dev/null; then
    (cd "$B" && sha256sum -c "$PKG.sha256")
    rm -rf "$B/out"
    mkdir -p "$B/out"
    tar -C "$B/out" -I zstd -xf "$B/$PKG"
    echo "Downloaded release $TAG into $B/out (./build-kernel.sh --build to compile it instead)"
    exit 0
fi
echo "No prebuilt $TAG to download, compiling (~30 min the first time)"

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
