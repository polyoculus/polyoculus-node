#!/bin/bash
# Names this Nano on every boot (polyoculus-identity.service, before networking starts).
# Cards are interchangeable, so the name comes from the hardware the card is plugged into:
#   1. the node in ansible/nodes.txt that lists this Nano's guide camera serial (the camera is
#      bolted to its telescope, so this is "which telescope am I")
#   2. the node that lists one of this board's MAC addresses
#   3. the name the card was flashed with
#   4. nano-<last 4 hex digits of the MAC>
# DRY_RUN=1 prints what it found and changes nothing; CAM_SERIAL=... pretends a camera is there.
set -euo pipefail
TABLE=${TABLE:-/home/alarm/polyoculus-node/ansible/nodes.txt}

# Wired MACs of this board (physical interfaces only)
macs=$(for d in /sys/class/net/*; do
    if [ -e "$d/device" ] && [ "$(cat "$d/type")" = 1 ]; then cat "$d/address"; fi
done | sort)

# Guide camera serial (CAM_SERIAL overrides, for testing); USB takes a few seconds after boot
cam=${CAM_SERIAL:-}
[ -n "$cam" ] || for _ in $(seq 10); do
    for v in /sys/class/video4linux/video*; do
        [ -e "$v/name" ] && grep -q "DMK" "$v/name" || continue
        cam=$(udevadm info -q property -p "$v" | sed -n 's/^ID_SERIAL_SHORT=//p')
        [ -n "$cam" ] && break 2
    done
    sleep 1
done

name=""
if [ -f "$TABLE" ]; then
    # camera match wins over MAC match, whatever the line order
    name=$(awk -v cam="${cam,,}" -v macs="${macs,,}" '
        BEGIN { n = split(macs, m, "\n"); for (i = 1; i <= n; i++) mac[m[i]] = 1 }
        { sub(/#.*/, "") }
        NF > 1 { for (i = 2; i <= NF; i++) { k = tolower($i)
            if (cam != "" && k == cam && !bycam) bycam = $1
            if (k in mac && !bymac) bymac = $1 } }
        END { print (bycam ? bycam : bymac) }' "$TABLE")
fi
current=$(cat /etc/hostname 2>/dev/null || true)
if [ -z "$name" ]; then
    if [ -n "$current" ] && [ "$current" != alarm ]; then
        name=$current
    else
        first=$(head -1 <<< "$macs")
        name=nano-$(tr -d : <<< "${first: -5}")
    fi
fi

if [ -n "${DRY_RUN:-}" ]; then
    echo "camera=${cam:-none} macs=$(tr '\n' ' ' <<< "$macs")-> $name"
    exit 0
fi

if [ "$name" != "$current" ]; then
    echo "$name" > /etc/hostname
    echo "polyoculus-identity: $current -> $name"
fi
echo "$name" > /proc/sys/kernel/hostname

# On the login screen: what to put in nodes.txt to pin this hardware to a name
mkdir -p /etc/issue.d
printf 'This Nano is %s. Guide camera: %s. Board MAC: %s.\n(ansible/nodes.txt maps camera serials and MACs to node names.)\n\n' \
    "$name" "${cam:-none}" "$(tr '\n' ' ' <<< "$macs")" > /etc/issue.d/polyoculus-identity.issue
