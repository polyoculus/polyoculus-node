# Running the fleet

Everything here runs from a laptop on the same network as the Nanos, in `ansible/`, using
Ansible through `uv` (nothing to install but `uv` and `rsync`). `ansible.cfg` there sets the
inventory (`nodes.txt`), SSH options and `forks = 8` (all Nanos in parallel).

```sh
cd ansible
alias ap='uvx --from ansible ansible-playbook'   # optional shorthands used below
alias an='uvx --from ansible ansible'
```

## Changing anything on the Nanos

Edit the repo, then:

```sh
ap site.yml                    # every Nano
ap site.yml --limit nano-03    # one Nano
ap site.yml --check --diff     # dry run: show what would change
```

`site.yml` brings each Nano to the state the repo describes and only changes what differs, so
it's safe to rerun any time. It also **pushes your checkout** (uncommitted changes included) to
`~/polyoculus-node` on each Nano and rebuilds the Python environments if dependencies changed.
So deploying new node code is the same command. Commit what you deploy, so the repo stays the
truth.

Never reflash to apply a change; reflashing is only for new or dead cards. Two exceptions don't
reach running Nanos through Ansible: edits to `os/flash-card.sh`/`os/firstboot.sh` (they only
affect future cards) and the kernel ([kernel.md](kernel.md#installing-a-new-kernel-on-running-nanos)).

**Removing something:** deleting a task or package from the repo does not remove it from the
Nanos. Change it to `state: absent` (or the equivalent), run site.yml, and only then delete it.

Which file to edit: see [ansible/README.md](../ansible/README.md).

## Commands on every Nano

```sh
an nanos -m ping                                   # who's up (and reachable over SSH)
an nanos -a "uptime"                               # any command, every Nano
an nanos -b -a "systemctl restart indiserver"      # -b: as root
an nanos -a "chronyc tracking"                     # clock offsets
an '~nano-0[1-4]' -a "df -h /"                     # a subset (~ = regex)
an nanos -b -a "systemctl poweroff"                # shut everything down
```

For interactive work on all of them, tmux with one pane per Nano:
`ssh alarm@nano-01.local` in each pane, then `Ctrl-b :setw synchronize-panes on` types into all
panes at once (`off` to stop).

## Updating packages

Arch Linux updates continuously. Never update Nanos by hand one at a time (`pacman -Syu` on one
Nano) or they drift apart. Use the rolling upgrade, which does one Nano, then the rest only if
that worked:

```sh
ap upgrade.yml --limit nano-01   # canary: observe with it for a night
ap upgrade.yml                   # then everyone
```

The kernel isn't a pacman package; see [kernel.md](kernel.md).

## Access

There are no passwords anywhere. Access is by SSH key:

- **Add a person:** they commit their public key as `ansible/files/authorized_keys/<name>.pub`
  (`ssh-keygen -t ed25519` makes one, `~/.ssh/id_ed25519.pub`), then run `ap site.yml`.
- **Remove a person:** delete their `.pub`, run `ap site.yml`. Each Nano gets exactly the keys
  in that folder.
- **Console:** keyboard + HDMI on the Nano, log in as `alarm`, no password.
- Your laptop must resolve `<name>.local` (mDNS): built into macOS; on Linux, systemd-resolved
  with mDNS enabled on your network connection, or avahi + nss-mdns.

**Off the lab network:** not set up. The repo can join the Nanos to Tailscale
(`tailscale_enabled: true` in `group_vars/nanos.yml`, plus a tailnet owned by a lab account with
the policy in [ansible/README.md](../ansible/README.md#tailscale)), but the group decided against
it for now.

## Node names

`ansible/nodes.txt` lists the nodes. It's both Ansible's host list and the table each Nano uses
to name itself at boot ([architecture.md](architecture.md#names)):

```
# name     guide camera serials / board MACs
nano-03    43120211
nano-04    00:04:4b:e5:a1:b2
nano-05
```

- **Pin a telescope to a name:** add its guide camera's serial (shown on the Nano's login
  screen, or `dmk.py info`) to the line, commit, `ap site.yml`, reboot that Nano.
- **A new node:** add a line. A Nano not in the table still works (it's `nano-<MAC>`), but your
  laptop's Ansible won't know about it until it's listed.
- **Swapping a card** between Nanos needs nothing: each Nano renames itself at boot.

## USB ports for the mount and mirror

The mount and FSM controller are both USB-serial adapters, which Linux numbers `ttyUSB0`,
`ttyUSB1` in whatever order they appear. To give them fixed names, pick one USB port on the Nano
for each, label it on every Nano, then record the port once:

1. Plug only the mount into its port, on any Nano.
2. `udevadm info -q property /dev/ttyUSB0 | grep ^ID_PATH=`
3. Put the value in `ansible/group_vars/nanos.yml` under `usb_ports.mount`. Same for `fsm`.
4. `ap site.yml`. Every Nano now has `/dev/mount` and `/dev/fsm` when those are plugged into
   their ports; `guide.py` and `fsm.py` use them by default.

## indiserver

Every Nano runs `indiserver` with the iOptron driver (`indi_ioptronv3_telescope`) on port 7624
from boot, so the mount can be driven locally (`guide.py`) or over the network (a scheduler
connecting to all eight). INDI has **no authentication**: anyone who can reach port 7624 can move
the mount, so keep Nanos on the lab network.

```sh
systemctl status indiserver
journalctl -u indiserver -f            # driver messages
sudo systemctl stop indiserver         # e.g. to run guide.py simulate on this Nano
```

## Logs

Logs live in RAM (`journal_storage: volatile` in `group_vars/nanos.yml`) to spare the SD card,
so they're lost on reboot. To keep them on a Nano you're debugging, set it to `persistent` and
run site.yml for that Nano (it then applies to all Nanos you run it on, so set it back after).

## Getting data off the Nanos

Captures go to `captures/` inside `~/polyoculus-node/camera` and `~/polyoculus-node/guide` on
each Nano. Ansible never touches them, but **a dead card takes them with it**, so copy them off
after every session:

```sh
for n in $(awk '!/^#/ && NF {print $1}' ansible/nodes.txt); do
    for d in camera guide; do
        rsync -a "alarm@$n.local:polyoculus-node/$d/captures/" "data/$n/$d/" 2>/dev/null ||
            echo "$n/$d: nothing copied (unreachable, or no captures)"
    done
done
```

(From the repo root; `data/` is yours to choose, and should be somewhere backed up.)

## Shutting down and powering off

```sh
an nanos -b -a "systemctl poweroff"
```

Wait ~20 s before cutting power. Pulling power from a running Nano usually survives (ext4
journal) but is how cards get corrupted.
