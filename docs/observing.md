# An observing session

What a night looks like with the current software. Each Nano is driven by hand over SSH; there
is no scheduler running all telescopes yet (indiserver on every Nano is the groundwork for one).

Commands run on a Nano (`ssh alarm@nano-03.local`) unless they start with `an`/`ap`, which run
from `ansible/` on a laptop (see [operations.md](operations.md) for those shorthands).

## Before dark

1. **Power and network.** Nanos on, Ethernet to a network with internet if possible (time and
   updates), cameras and serial adapters in their labeled ports.
2. **Fleet check** from the laptop:
   ```sh
   an nanos -m ping                                  # everyone answers
   an nanos -a "chronyc tracking" | grep -E "nano|System time"   # clocks agree (offsets ~ms or better)
   an nanos -a "systemctl is-active indiserver"      # mount servers up
   an nanos -a "ls -l /dev/mount /dev/fsm"           # serial adapters in the right ports
   ```
3. **Camera check** on each Nano:
   ```sh
   cd ~/polyoculus-node/camera
   .venv/bin/python dmk.py info          # camera found, controls listed
   ```
   "DMK 33UX273 not found" means it isn't on a USB3 port, or isn't plugged in.

## Point the mount

`guide.py` assumes the mount is already unparked, pointed and tracking. Until there's a mount
command-line tool, do it with `MountOperator` from `mount/`:

```sh
cd ~/polyoculus-node/mount
uv run python - <<'EOF'
import sys; sys.path.insert(0, "src")
from MountOperator import MountOperator
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD
from mountaction import MountMode

m = MountOperator(config=MountConfiguration(DEVICE_PORT="/dev/mount"))
m.connect()
m.unpark()
m.move_coord(EOD_COORD(5.919, 7.407), mode=MountMode.TRACK)  # RA hours, Dec degrees (here Betelgeuse)
print(m.get_EOD_COORD())
m.disconnect()
EOF
```

`move_coord` slews and then tracks. `set_tracking(True/False)`, `park()`, `go_home()` and
`move_emergency_abort()` are there too ([mount/README.md](../mount/README.md)).

## Focus

```sh
cd ~/polyoculus-node/camera
.venv/bin/python dmk.py focus -e 10000      # live sharpness number; turn focus to maximize it
```

## Guide

```sh
cd ~/polyoculus-node/guide
uv run guide.py calibrate              # once per night, or after the camera moves
uv run guide.py run                    # hold the star where it is now; Ctrl-C to stop
uv run guide.py run --target 712 540   # hold it on a pixel (e.g. the fiber)
```

Calibration pulses the mount west, then north, and measures how far the star moves; it's saved
in `captures/` and reused by `run`. Each `run` writes a CSV log of positions and corrections to
`captures/` and prints the RMS error at the end. Exposure is `-e` in microseconds (default
100 ms). See [guide/README.md](../guide/README.md) for how it works and the tuning knobs.

## Fast steering mirror

For the fiber feed: calibrate the mirror against the camera once per session (after anything in
the optics moves), then put or hold the spot on a pixel.

```sh
cd ~/polyoculus-node/camera
.venv/bin/python dmk.py fsm calibrate          # 7x7 voltage grid -> captures/fsm-cal.json
.venv/bin/python dmk.py fsm goto 700 400       # put the spot on a pixel
.venv/bin/python dmk.py fsm track -t 30        # hold it there for 30 s (PI loop) -> csv + plot
```

Details in [camera/README.md](../camera/README.md).

## End of the night

1. Stop guiding (Ctrl-C), then park each mount (same snippet as above with `m.park()` instead
   of the slew).
2. **Copy the captures off** every Nano: the loop in
   [operations.md](operations.md#getting-data-off-the-nanos). A card can die any night.
3. Shut down before cutting power: `an nanos -b -a "systemctl poweroff"`.

## Testing without the sky

`guide.py simulate` runs the whole guiding loop against INDI's telescope simulator and a
simulated camera (5" periodic error plus drift), and reports unguided vs guided RMS. It needs
the simulator on port 7624, so on a Nano stop the real server first:

```sh
sudo systemctl stop indiserver
indiserver indi_simulator_telescope &
cd ~/polyoculus-node/guide && uv run guide.py simulate
kill %1; sudo systemctl start indiserver
```
