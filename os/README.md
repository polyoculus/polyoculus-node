# os/

Making an SD card into a Nano node. The walkthrough is [docs/new-node.md](../docs/new-node.md);
this is the reference.

| File | Runs on | What |
|---|---|---|
| `build-kernel.sh` | laptop | get the kernel into `build/out/`: download the published release or compile |
| `flash-card.sh` | laptop, sudo | write Arch + kernel + this repo + first-boot services to a card |
| `firstboot.sh` | Nano, once | installed as `/usr/local/bin/nano-firstboot`; sets the Nano up |
| `nano-firstboot.service` | Nano | runs firstboot.sh after network-online, retries every 60 s |
| `identity.sh` | Nano, every boot | installed as `/usr/local/bin/polyoculus-identity`; picks the hostname |
| `polyoculus-identity.service` | Nano | runs identity.sh before networking |
| `kernel/config` | laptop | the kernel config ([docs/kernel.md](../docs/kernel.md)) |
| `build/` | laptop | downloads, kernel source and output (git-ignored) |

## build-kernel.sh

```sh
./build-kernel.sh            # download release kernel-<KVER>-<config hash>, or compile
./build-kernel.sh --build    # compile even if a release exists
./build-kernel.sh --publish  # package build/out and create the GitHub release
```

Also downloads and GPG-verifies the Arch Linux ARM tarball into `build/` (needed by
flash-card.sh). Settings at the top: `KVER`, `ALARM_URL`, `ALARM_KEY`, `GH_REPO`. Download and
publish need `gh` logged in. Details: [docs/kernel.md](../docs/kernel.md).

## flash-card.sh

```sh
sudo ./flash-card.sh /dev/sdX [name]
sudo TS_AUTHKEY=tskey-... ./flash-card.sh /dev/sdX [name]   # only matters with tailscale_enabled
```

Refuses anything that isn't a removable disk, shows it, and asks for `yes`. Then:

1. Old JetPack card (has partitions): reformats partition 1 and keeps NVIDIA's layout. Blank
   card: one GPT partition. `mkfs.ext4` without `metadata_csum_seed`/`orphan_file` (U-Boot can't
   read them).
2. Unpacks Arch Linux ARM; installs `build/out/Image-nano`, the dtb and the modules.
3. Writes `/boot/extlinux/extlinux.conf` (root by `PARTUUID`, `module_blacklist` for the SError
   drivers, forced HDMI mode, serial + screen console), `/etc/fstab` (`/` with `noatime`), UTC.
4. Hostname only if a name was given (else the identity service names the Nano at boot); warns
   if the name isn't in `ansible/nodes.txt`.
5. Accounts: `alarm` with an empty password, `root` locked.
6. Copies this repo as it is on the laptop (tracked + untracked, non-ignored files, and `.git`)
   to `/home/alarm/polyoculus-node`.
7. Installs and enables `nano-firstboot.service` and `polyoculus-identity.service`; stores
   `TS_AUTHKEY` in `/root/ts-authkey` (mode 600, deleted after first boot) if given.

## firstboot.sh (nano-firstboot.service)

Output goes to the console and `/var/log/nano-firstboot.log`; `/etc/issue` (the login screen)
says RUNNING / FAILED / done. Steps: wait for internet (polls `mirror.archlinuxarm.org`) ->
wait up to 5 min for NTP -> `pacman-key --init/--populate` -> remove `linux-aarch64` -> `pacman
-Syu python sudo git ansible` -> `ansible-playbook site.yml` for this Nano, local connection ->
disable itself, reboot. Any failure exits non-zero and systemd retries a minute later; every
step is safe to repeat.

## identity.sh (polyoculus-identity.service)

Sets the hostname at every boot from `ansible/nodes.txt` (the copy in
`/home/alarm/polyoculus-node`, kept current by Ansible): the node listing this Nano's guide
camera serial, else one of its MACs, else the flashed name, else `nano-<last 4 of MAC>`. Waits up
to 10 s for the camera to enumerate. Writes `/etc/issue.d/polyoculus-identity.issue` (the camera
serial and MAC on the login screen).

Testing it anywhere without changing anything:

```sh
DRY_RUN=1 TABLE=../ansible/nodes.txt ./identity.sh
DRY_RUN=1 CAM_SERIAL=43120211 TABLE=../ansible/nodes.txt ./identity.sh   # pretend a camera
```
