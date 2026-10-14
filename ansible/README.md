# ansible/

Everything on a Nano after the OS is unpacked: packages, accounts, time, hardware names, INDI,
the node software. The same playbook runs on a card's first boot (locally, from the copy of the
repo on the card) and from a laptop afterwards (over SSH). How to run it day to day:
[docs/operations.md](../docs/operations.md).

```sh
uvx --from ansible ansible-playbook site.yml [--limit nano-03] [--check --diff]
```

## Files

| File | What |
|---|---|
| `site.yml` | the playbook: roles base, sd-wear, hardware, tailscale, indi, software, in that order |
| `upgrade.yml` | rolling `pacman -Syu`: first Nano alone, then the rest if it worked |
| `nodes.txt` | the nodes: name, then camera serials / board MACs that make a Nano that node |
| `inventory.py` | inventory from `nodes.txt`: group `nanos`, each host at `<name>.local`, user `alarm`. On first boot `POLYOCULUS_LOCAL_HOST` adds the Nano itself as a local connection |
| `ansible.cfg` | inventory, `forks = 8`, Python path, SSH options (accept new host keys, since reflashed cards get new ones; refuse changed ones) |
| `group_vars/nanos.yml` | every setting (below) |
| `files/authorized_keys/*.pub` | the SSH keys allowed on every Nano |

## Settings (`group_vars/nanos.yml`)

There is no per-node configuration: these apply to every Nano.

| Variable | Default | Meaning |
|---|---|---|
| `timezone` | `UTC` | observatory convention |
| `base_packages` | sudo, git, vim, htop, rsync, python, uv, chrony, zram-generator, fastfetch, tmux, picocom, usbutils, i2c-tools, lm_sensors, ... | pacman packages on every Nano |
| `ssh_password_auth` | `false` | nodes have no passwords; keys only |
| `tailscale_enabled` | `false` | join a tailnet (off: group decision); `false` also removes Tailscale |
| `journal_storage` | `volatile` | logs in RAM; `persistent` keeps them on the card (debugging) |
| `usb_ports.mount`, `usb_ports.fsm` | `""` | udev `ID_PATH` of the USB port for the mount / mirror adapter; empty = no symlink |

## Roles

### base
- Packages (`base_packages`); removes Arch's stock kernel package (`linux-aarch64`): nodes boot
  our own kernel, see [docs/kernel.md](../docs/kernel.md).
- `polyoculus-identity` script and service (from `os/`): the Nano names itself at every boot
  from `nodes.txt`. Ansible never sets the hostname.
- Timezone, `en_US.UTF-8` locale.
- Time: systemd-timesyncd off, chronyd on, `/etc/chrony.conf` from `templates/chrony.conf.j2`:
  the internet pool, every other Nano as `<name>.local`, orphan mode (`local stratum 10
  orphan`) so the fleet agrees without internet, `allow` for the lab LAN ranges and the tailnet.
- zram swap (half of RAM).
- Accounts: `alarm` in `wheel`, `uucp` (serial ports), `video` (camera), empty password; root
  locked; `%wheel ALL=(ALL:ALL) NOPASSWD: ALL`.
- SSH: `alarm`'s `authorized_keys` is exactly `files/authorized_keys/*.pub` (skipped if that
  folder is empty, so nobody is locked out); `PasswordAuthentication` per `ssh_password_auth`,
  `PermitRootLogin no`.
- mDNS: `MulticastDNS=yes` in resolved and in drop-ins for Arch's `en.network`/`eth.network`, so
  the Nano answers to `<name>.local`.

### sd-wear
- journald `Storage=` per `journal_storage`, capped at 64 MB.
- Removes any `rootflags=noatime` from `extlinux.conf` (it stops the Nano booting) and mounts
  `/` with `noatime` from `/etc/fstab` (uses the root `PARTUUID` from the kernel command line).

### hardware
- `/etc/udev/rules.d/70-polyoculus-serial.rules`: `/dev/mount`, `/dev/fsm` by USB port
  (`usb_ports`).
- `/etc/udev/rules.d/50-usb-no-autosuspend.rules`: USB devices never autosuspend.
- `/etc/systemd/system.conf.d/10-watchdog.conf`: `RuntimeWatchdogSec=30s` (systemd pets the
  PMIC's watchdog; a hung Nano reboots), `RebootWatchdogSec=2min`.

### tailscale
Off (`tailscale_enabled: false`): stops and removes tailscale. On: installs it, runs
tailscaled, joins with `TS_AUTHKEY` from the environment
(`tailscale up --hostname=<name> --advertise-tags=tag:nano --ssh`), and turns on Tailscale SSH on
Nanos that joined before. See [Tailscale](#tailscale) for the tailnet side.

### indi
- `libindi` (indiserver and `indi_ioptronv3_telescope` for the CEM70).
- `indiserver.service`: `indiserver -p 7624 indi_ioptronv3_telescope` as `alarm`, at boot,
  restarted on failure.

### software
- `base-devel`, `swig` (pyindi-client compiles on the Nano: no aarch64 wheel), `v4l-utils`
  (`dmk.py` uses `v4l2-ctl`).
- Pushes the repo from the machine running Ansible to `/home/alarm/polyoculus-node` with rsync
  (as `alarm`; `.gitignore`d files, `captures/` and `.venv/` are left alone; skipped on first
  boot, which runs from the copy flash-card.sh made). Needs `rsync` on the laptop.
- `uv sync --locked` in `guide/` and `mount/`; a venv plus `requirements.txt` in `camera/`.
  System Python only (`UV_PYTHON_PREFERENCE=only-system`).

## Writing tasks

- Every task must be idempotent: a second run reports `changed=0`.
- Removing something: deleting the task doesn't remove it from Nanos. Change it to
  `state: absent` (or equivalent), run it, then delete it later.
- No per-node settings (no `host_vars/`): any card works in any Nano.
- Check before committing:
  ```sh
  uvx --from ansible ansible-playbook site.yml --syntax-check
  uvx --from ansible-lint ansible-lint site.yml
  ```
  (ansible-lint reports `community.general.pacman` as unknown because its own install lacks the
  collection; that one is harmless.)
- Variables registered inside a role are prefixed with the role name (`base_`, `software_`, ...).

## Tailscale

If the group ever wants it: a tailnet owned by a **lab** account (not a student's), then

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
2. Settings -> Keys -> auth key: reusable, pre-approved, tags `tag:nano`. Tagged devices don't
   expire; the key itself does (90 days max), which only matters for joining new cards.
3. `tailscale_enabled: true`, then `TS_AUTHKEY=tskey-... uvx --from ansible ansible-playbook site.yml`
   (or `sudo TS_AUTHKEY=tskey-... os/flash-card.sh ...` for new cards).
