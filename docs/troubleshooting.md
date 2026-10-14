# Troubleshooting

## Reading a Nano's logs when it won't boot

A freshly flashed card keeps its logs on the card (Ansible switches to RAM-only logs at the end of
first boot). Put the card in a laptop; it auto-mounts. Then:

```sh
journalctl --directory=/run/media/$USER/APP/var/log/journal/*/ -o short-monotonic | tail -50
journalctl --directory=... -k            # kernel messages only
```

The Nano has no clock battery, so dates in early-boot logs are wrong; `-o short-monotonic`
shows seconds since boot instead. Logs are only written to the card a few seconds into boot
(the journal flush), so a crash before that leaves nothing; and a crash *after* it leaves the
log ending a little before the crash. The panic text itself is only on the screen: take a photo.

On a Nano that's set up, logs are in RAM. To keep them across a crash, set
`journal_storage: persistent` in `ansible/group_vars/nanos.yml` and run site.yml for that Nano.

**Serial console:** if nothing appears on HDMI at all, a 3.3 V USB-serial adapter (FTDI or
CP2102, ~$10) on the Nano's debug UART (the TX/RX/GND pins of the J50 header on the B01 carrier board) shows U-Boot
and the kernel at 115200 baud: `picocom -b 115200 /dev/ttyUSB0`. The kernel command line already
has `console=ttyS0,115200n8`.

## Boot problems

| What you see | Cause | Fix |
|---|---|---|
| Nothing on HDMI, fan/LED on | U-Boot can't find or read the card | Reflash; check the card works in the laptop; board must have run JetPack 4.5+ once (QSPI firmware) |
| HDMI goes black right after the kernel starts | monitor hotplug quirk | Already handled (`video=HDMI-A-1:...e`); try another monitor/cable |
| `unknown parameter 'noatime'` from every filesystem, then `VFS: Unable to mount root fs` | `rootflags=noatime` on the kernel command line (old cards/old sd-wear role) | Remove ` rootflags=noatime` from `/boot/extlinux/extlinux.conf` on the card; current flash-card.sh and site.yml do this, and put `noatime` in `/etc/fstab` instead |
| `Kernel panic - not syncing: Asynchronous SError Interrupt` a few seconds after boot | a driver touching powered-off hardware; on boards that ran JetPack 4.6 (L4T R32.7.x) the firmware locks the power controller (`tegra-pmc: access to PMC is restricted to TZ`) | flash-card.sh blocks the four culprits (`module_blacklist=snd_hda_tegra,tegra210_adma,tegra_aconnect,nouveau`); on an older card add that to the `APPEND` line in extlinux.conf |
| Waits forever for the root device | kernel can't reach the SD card | Must be our kernel (`Image-nano`), not Arch's stock one: see [kernel.md](kernel.md) |
| `max77620 ... Failed to create device link` | harmless warning | nothing |
| Login screen says first-boot setup **FAILED** | see below | |

## First boot didn't finish

The login screen says RUNNING / FAILED (retrying every minute) / done. Log in as `alarm` (no
password) and read `/var/log/nano-firstboot.log`.

- **Stuck at "waiting for the network":** no internet over Ethernet. Check the cable/port; the
  Nano needs DHCP and a route out (`ip addr`, `ping -c1 archlinux.org`).
- **Stuck at "waiting for NTP":** it continues after 5 minutes anyway. If pacman then complains
  about signatures "from the future", the clock is wrong: `sudo date -s '2026-10-14 12:00'`.
- **pacman errors** (mirror down, conflicting files): fix by hand, it retries by itself:
  `sudo pacman -Syu`.
- **Ansible task failed:** the log shows which. Fix the repo, then either reflash, or (if the
  Nano is reachable over SSH) just run site.yml from the laptop for that Nano and then
  `sudo systemctl disable --now nano-firstboot`.

## Can't reach a Nano

- **`ssh: Could not resolve hostname nano-03.local`:** mDNS. Is the Nano on the same network
  (not across a router)? Does your laptop do mDNS (`resolvectl status` shows `+mDNS` on the
  connection you're using)? Which name did the Nano pick? It's on its login screen
  (`nano-<MAC>` if it isn't in `nodes.txt`). As a stopgap, use its IP (from the screen,
  `ip addr`, or the router's DHCP leases): `ssh alarm@<ip>`, and for Ansible
  `ap site.yml --limit nano-03 -e ansible_host=<ip>`.
- **`Permission denied (publickey)`:** your key isn't on the Nano. Commit
  `ansible/files/authorized_keys/<you>.pub` and have someone whose key works run site.yml, or
  log in at the console and add it to `~/.ssh/authorized_keys` by hand.
- **SSH asks for a password:** the Nano is from before the no-password setup: see
  [new-node.md](new-node.md#cards-flashed-before-the-no-password-setup-oct-2026).
- **`ansible nanos -m ping` shows some unreachable:** they're off, renamed (check its login
  screen vs `nodes.txt`), or not on the network.

## Ansible errors

- **`rsync: command not found`** (Repo synced task): install rsync on your laptop.
- **`uv sync` fails building pyindi-client:** needs `base-devel`, `swig` and `libindi` on the
  Nano (the software and indi roles install them); read the compiler error in the output.
- **A task "changed" every run:** a bug in the role (should be idempotent); fine to ignore once,
  worth fixing.
- **`community.general.pacman` not found** from `ansible-lint`: lint's own install lacks the
  collection; harmless. `uvx --from ansible` (full Ansible) has it.

## Hardware

- **`DMK 33UX273 not found`:** not in a USB3 port, or unplugged (`lsusb` should list The Imaging
  Source). If it shows in `lsusb` but `dmk.py` can't open it: `alarm` must be in `video` (`id`).
- **No `/dev/mount` or `/dev/fsm`:** `usb_ports` in `group_vars/nanos.yml` empty, or the
  adapter is in a different port than the one recorded ([operations.md](operations.md#usb-ports-for-the-mount-and-mirror)).
  `ls -l /dev/serial/by-path/` shows what's where.
- **`Permission denied: '/dev/ttyUSB0'`:** `alarm` must be in `uucp`.
- **guide.py can't connect to the mount:** `systemctl status indiserver`, `journalctl -u indiserver`.
  `guide.py simulate` needs the real indiserver stopped (port 7624).
- **Camera or adapter drops out mid-session:** USB autosuspend is already off; suspect the cable
  or power (a 4 A supply, not micro-USB).

## The Nano rebooted by itself

The hardware watchdog reboots a Nano that hangs for 30 s. `journalctl -b -1` (if logs are
persistent) shows what happened before. Repeated hangs: check power supply, temperature
(`sensors`), and the card.

## SD card errors

`EXT4-fs error`, `I/O error`, files that vanish, a card that goes read-only: the card is failing
or was corrupted by a power cut. Copy off what you can, then flash a new card (high endurance)
and let the Nano rebuild itself. Don't try to repair a card that's going bad.

## Clocks disagree

`chronyc sources` on each Nano: `*` marks the source in use. With internet everyone should use
the pool; without it, one Nano (orphan mode) serves the rest. If a Nano lists no reachable
sources, it can't resolve or reach the others (mDNS, network), or chronyd isn't running.
