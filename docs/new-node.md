# Setting up a Nano (or replacing a dead card)

About 2 minutes of your time plus ~20 minutes of the Nano setting itself up.

## What you need

- An **x86_64 Linux** laptop with: `git`, [`uv`](https://docs.astral.sh/uv/) (runs Ansible),
  `rsync`, `bsdtar` (libarchive), `zstd`, and `gh` logged in to GitHub (downloads the prebuilt
  kernel from this private repo's releases). Arch: `sudo pacman -S git uv rsync libarchive zstd github-cli`.
- An SD card: 32 or 64 GB **High Endurance** (Samsung PRO Endurance, SanDisk High Endurance).
  Cheap cards are the most likely thing to kill a node.
- A USB SD card reader.
- For the Nano: a **5 V 4 A barrel-jack** supply (5.5 x 2.1 mm, center positive) with the
  **J48 jumper** fitted (without it the Nano ignores the barrel jack), Ethernet to a network
  **with internet**, and optionally HDMI + keyboard to watch.
- The board must have run NVIDIA's JetPack 4.5 or newer at least once (all the lab's boards
  have), so its bootloader firmware is current.

## 1. Get the kernel

```sh
cd os
./build-kernel.sh
```

This downloads the published kernel matching this repo's kernel version and config into
`os/build/out/` (seconds). If there's no matching release (someone changed the config), it
compiles instead (~10-40 min depending on the machine; build deps are listed at the top of the
script). Also downloads and signature-checks the Arch Linux ARM image. Only needed once per
laptop, and again after kernel changes.

## 2. Find the card

Plug the card in and check which device it is. **Getting this wrong erases the wrong disk**:
the script refuses non-removable disks, but check anyway.

```sh
lsblk -o NAME,SIZE,TRAN,RM,LABEL,MOUNTPOINTS
```

The card is the `usb`/`RM=1` disk of the right size, usually `/dev/sda`.

### If it's an old lab card

Old cards run NVIDIA's Ubuntu (JetPack) and may hold data. Before wiping, look at
`/home/*/` on its first partition and copy anything worth keeping somewhere permanent, e.g.:

```sh
M=/run/media/$USER/<the card's mount>      # it usually auto-mounts
cat $M/etc/hostname $M/etc/nv_tegra_release
mkdir -p ~/polyoculus-backups/$(cat $M/etc/hostname)
(cd $M/home && tar --exclude='*/.cache' -cf - .) | tar -xf - -C ~/polyoculus-backups/$(cat $M/etc/hostname)
```

**Orin cards** (`nv_tegra_release` says `R36`, or `/boot` has `tegra234` files) belong to Jetson
Orins. This repo doesn't support Orins yet: don't flash them.

## 3. Flash

```sh
sudo ./flash-card.sh /dev/sda            # the Nano names itself at boot
sudo ./flash-card.sh /dev/sda nano-03    # or give the card a name
```

It shows the disk and asks you to type `yes`. Then it:

- reformats the card's first partition (keeping NVIDIA's partition layout on old JetPack cards;
  a blank card gets one partition),
- unpacks Arch Linux ARM and installs the kernel, its modules and `extlinux.conf`,
- sets an **empty** password for `alarm` and locks `root`,
- copies **this repo as it is on your laptop** (uncommitted changes too) to
  `/home/alarm/polyoculus-node`,
- installs `nano-firstboot.service` and `polyoculus-identity.service`.

Naming: give a name only if this card should be a specific node before the hardware table knows
it (see [Names](architecture.md#names)). Without one, the Nano calls itself what
`ansible/nodes.txt` says for its camera or board, else `nano-<MAC>`.

Unmount before pulling the card (pulling a mounted card can corrupt it):

```sh
udisksctl power-off -b /dev/sda
```

## 4. First boot

Put the card in the Nano, plug in **Ethernet**, optionally HDMI, then power. On screen:

1. `waiting for the network (plug in Ethernet)`: it needs internet. It waits forever, without
   harm, until it gets some.
2. `waiting for NTP to set the clock`: the Nano has no clock battery.
3. `package keys`, `full update`: pacman setup and a full system update (the longest step).
4. `ansible/site.yml for <name> (local run)`: the same playbook you run from a laptop, including
   building the Python environments (compiles pyindi-client, a few minutes).
5. `done`, then it reboots by itself.

If any step fails it retries every minute. The login screen shows whether setup is
**RUNNING**, **FAILED** (retrying) or done, and the full log is `/var/log/nano-firstboot.log`.
Total ~20 minutes, mostly downloads.

When it's done the login screen says `<name>: set up from polyoculus-node. Log in as alarm (no
password).` and shows the Nano's guide camera serial and MAC address.

## 5. Check it

From your laptop on the same network:

```sh
ssh alarm@nano-03.local          # your key must be in ansible/files/authorized_keys/
```

On the Nano:

```sh
systemctl is-active indiserver chronyd      # both "active"
chronyc sources                             # a time source marked *
ls -l /dev/watchdog*                        # the watchdog exists
id                                          # alarm in wheel, uucp, video
cd ~/polyoculus-node/guide && uv run pytest # the node software runs
```

## 6. Name it (once the hardware is on the telescope)

On the login screen (or `cat /etc/issue.d/polyoculus-identity.issue`), note the guide camera
serial. Add it to that telescope's line in `ansible/nodes.txt`:

```
nano-03   43120211
```

Commit, then push the table to every Nano and reboot this one (or wait for its next boot):

```sh
cd ansible && uvx --from ansible ansible-playbook site.yml
```

## Cards flashed before the no-password setup (Oct 2026)

Cards flashed before commit `afc622e` have a password for `alarm` and `root` and no node
software. Either reflash them, or convert them in place with one Ansible run using that old
password (needs `sshpass` on the laptop):

```sh
cd ansible && uvx --from ansible ansible-playbook site.yml -k -K --limit nano-03
```

`-k` asks for the SSH password and `-K` for sudo's (the same one). After that run, no flags are
needed ever again.
