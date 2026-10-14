#!/usr/bin/env python3
"""Ansible inventory: the nodes in nodes.txt, each reached as <name>.local (mDNS).

On a card's first boot, firstboot.sh sets POLYOCULUS_LOCAL_HOST so the Nano is in the inventory
(as a local connection) even before it has a line in nodes.txt.
"""
import json
import os
import sys
from pathlib import Path

names = []
for line in (Path(__file__).parent / "nodes.txt").read_text().splitlines():
    fields = line.split("#", 1)[0].split()
    if fields and fields[0] not in names:
        names.append(fields[0])

hostvars = {n: {"ansible_host": f"{n}.local"} for n in names}
local = os.environ.get("POLYOCULUS_LOCAL_HOST")
if local:
    if local not in names:
        names.append(local)
    hostvars[local] = {"ansible_connection": "local"}

if "--host" in sys.argv:
    print(json.dumps(hostvars.get(sys.argv[-1], {})))
else:
    print(json.dumps({
        "nanos": {"hosts": names, "vars": {"ansible_user": "alarm"}},
        "_meta": {"hostvars": hostvars},
    }))
