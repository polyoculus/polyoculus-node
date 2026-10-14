# mount (pyMountOperator)

Python control of an INDI telescope mount: the lab's iOptron CEM70s through the
`indi_ioptronv3_telescope` driver, via pyindi-client. `guide/` uses it for guide pulses; it's
also how to point a mount by hand ([docs/observing.md](../docs/observing.md#point-the-mount)).

It talks to an **indiserver**, not to the serial port directly: on a node,
`indiserver.service` runs the iOptron driver on port 7624 from boot. Elsewhere, start one:
`indiserver -v indi_ioptronv3_telescope` (or `indi_simulator_telescope` to test without a mount).

## Use

```python
import sys; sys.path.insert(0, "src")      # from mount/; guide/ sets this up for itself
from MountOperator import MountOperator
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD
from cardinalDirection import CardinalDirection

m = MountOperator(config=MountConfiguration(DEVICE_PORT="/dev/mount"))
m.connect()                                   # server, device, port/baud, CONNECT
m.unpark()
m.move_coord(EOD_COORD(5.919, 7.407))         # RA hours, Dec degrees (of date); slew then track
m.guide(CardinalDirection.West, ms=500)       # guide pulse
print(m.get_EOD_COORD())
m.park()
m.disconnect()
```

### MountOperator

| Method | |
|---|---|
| `connect()` / `disconnect()` | connect to indiserver, wait for the device, set `DEVICE_PORT` and baud rate if the driver has them, connect the mount |
| `unpark()` / `park()` | park also stops tracking; `wait=False` returns immediately |
| `set_tracking(on)` | sidereal tracking on/off |
| `move_coord(coord, mode=MountMode.TRACK)` | point at RA/Dec: `TRACK` slews then tracks, `SLEW` just slews, `SYNC` tells the mount it's already there |
| `get_EOD_COORD()` | current pointing (RA hours, Dec degrees, JNow) |
| `guide(direction, ms)` | timed guide pulse at the guide rate |
| `move_dir(direction, timeout)` + `set_slew_speed(n)` | manual motion for a number of seconds |
| `go_home()` | the mount's home position |
| `move_abort_on()` / `move_abort_off()` | stop motion gracefully / clear the abort |
| `move_emergency_abort()` | stop as fast as possible |

### MountConfiguration

| Field | Default | |
|---|---|---|
| `INDI_HOST`, `INDI_PORT` | `localhost`, `7624` | the indiserver (a remote Nano's works too: `nano-03.local`) |
| `DEVICE_NAME` | `iOptronV3` | INDI device name (`Telescope Simulator` for the simulator) |
| `DEVICE_PORT` | `None` | serial port; `None` keeps the driver's own. On a node: `/dev/mount` |
| `BAUD_RATE` | `115200` | |
| `TIMEOUT`, `SLEW_TIMEOUT` | `30`, `180` s | property waits, slews/parks |

`src/main.py` is an old demo (moves the mount N/W/S/E, then home).

## Setup and tests

```sh
uv sync                 # on a node, Ansible already did this
uv run pytest           # unit tests: PyIndi is mocked, no server needed
```

`uv.lock` is the source of truth for dependencies (`requirements.txt` is an old `pip freeze`).
pyindi-client compiles from source: it needs `swig`, a C++ compiler and libindi's headers
(`libindi` on Arch, `libindi-dev` on Debian/Ubuntu).

To try it against INDI's simulator:

```sh
indiserver indi_simulator_telescope &
uv run python -c "import sys; sys.path.insert(0,'src')
from MountOperator import MountOperator; from mountConfiguration import MountConfiguration
m = MountOperator(config=MountConfiguration(DEVICE_NAME='Telescope Simulator')); m.connect(); m.unpark(); print(m.get_EOD_COORD())"
```

## API docs (Sphinx)

Docstrings are written for Sphinx autodoc:

```sh
uv run --with sphinx sphinx-apidoc -o docs/source/api src
uv run --with sphinx make -C docs html        # docs/_build/html; latexpdf needs LaTeX
```

Rerun `sphinx-apidoc` after adding or removing source files. Format code with
[Ruff](https://docs.astral.sh/ruff/formatter/) (`uvx ruff format`).

## Not done yet

- A command-line tool for pointing/parking (today: the snippet above).
- Backlash compensation, if the mount/driver doesn't handle it.
