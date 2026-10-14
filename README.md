# polyoculus-node

Everything that runs on a PolyOculus telescope node: one of the lab's original 2019 Jetson
Nanos (p3450, 4 GB), each driving one telescope's mount, guide camera and fast steering mirror.
Covers the OS (mainline Linux 7.1 + Arch Linux ARM, replacing NVIDIA's end-of-life Ubuntu
18.04), configuration of the whole fleet, and the lab's node software.

```
os/          make an SD card into a node: kernel, flashing, first boot, self-naming
ansible/     everything on a Nano after that: packages, time, hardware, INDI, node software
mount/       iOptron CEM70 control over INDI (was pyMountOperator)
camera/      DMK 33UX273 guide camera + piezo fast steering mirror (was dmk-camera)
guide/       autoguiding: camera centroid -> mount guide pulses (+ an INDI-simulator test)
docs/        how it all works and how to run it
```

`mount/` and `camera/` were separate repos; they were imported with their full history.

## Documentation

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | how a node works: boot, services, names, time, access |
| [docs/new-node.md](docs/new-node.md) | flashing a card for a new Nano or replacing a dead one |
| [docs/operations.md](docs/operations.md) | running the fleet: deploying changes, updates, access, names, data |
| [docs/observing.md](docs/observing.md) | an observing night: pointing, focus, guiding, the mirror |
| [docs/troubleshooting.md](docs/troubleshooting.md) | boot problems, unreachable Nanos, hardware, cards |
| [docs/kernel.md](docs/kernel.md) | the custom kernel: why, building, publishing, updating |
| [os/README.md](os/README.md), [ansible/README.md](ansible/README.md) | reference: every script, role and setting |
| [mount/](mount/README.md), [camera/](camera/README.md), [guide/](guide/README.md) | the node software |

## The rules

**Cards are interchangeable.** The Nanos are identical boards, and a Nano names itself at every
boot from the hardware it's attached to: `ansible/nodes.txt` maps guide camera serials (the
camera stays with its telescope) and board MACs to node names. Put any card in the Nano on
telescope 3 and it becomes that node. There is no other per-node configuration anywhere.

**Nothing lives only on the SD card.** SD cards die. Every Nano is rebuildable from this repo
in ~20 minutes, so observation data and calibration files get copied off after every session.
Keep a pre-flashed spare card at the observatory.

**No passwords.** Nodes outlive the people who set them up, so there is nothing to remember or
hand over: `alarm` logs in at the console with no password, root is locked, sudo asks for
nothing, and SSH accepts the keys in `ansible/files/authorized_keys/`.

## Quick start

A new card (x86_64 Linux laptop with `uv`, `rsync` and `gh`; details in
[docs/new-node.md](docs/new-node.md)):

```sh
cd os
./build-kernel.sh                 # downloads the published kernel
sudo ./flash-card.sh /dev/sdX     # check the device with lsblk first!
```

Put it in a Nano with Ethernet (internet) and power it on; it sets itself up and reboots
(~20 min). Then, from the laptop on the same network:

```sh
ssh alarm@nano-03.local                                    # no password: your key
cd ansible && uvx --from ansible ansible-playbook site.yml # push any repo change to every Nano
```
