"""Autoguide a telescope node: the DMK guide camera steers the mount with guide pulses.

    uv run guide.py calibrate                # once per night, or after the camera moves
    uv run guide.py run                      # hold the star where it is now
    uv run guide.py run --target 712 540     # hold it on a pixel (e.g. the fiber)
    uv run guide.py simulate                 # end-to-end test against indi_simulator_telescope

indiserver must be running with the mount driver: `indiserver indi_ioptronv3_telescope`
(or `indi_simulator_telescope` for simulate).
"""

import argparse
import csv
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "mount" / "src"), str(HERE.parent / "camera")]

import numpy as np  # noqa: E402
from loguru import logger  # noqa: E402

import guider  # noqa: E402
from coordinate import EOD_COORD  # noqa: E402
from MountOperator import MountOperator  # noqa: E402
from mountConfiguration import MountConfiguration  # noqa: E402

OUT = HERE / "captures"
CAL = OUT / "guide-cal.json"


def connect(device, port=None):
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # INDI chatter off; the guider prints its own lines
    mount = MountOperator(config=MountConfiguration(DEVICE_NAME=device, DEVICE_PORT=port))
    mount.connect()
    return mount


def save_log(records, name):
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "x_px", "y_px", "err_x_px", "err_y_px", "west_ms", "north_ms"])
        w.writerows(records)
    return path


def cmd_calibrate(a):
    from dmk import Camera
    mount, cam = connect(a.device, a.port), Camera(exposure_us=a.exposure)
    try:
        cal = guider.calibrate(mount, cam, pulse_ms=a.pulse, steps=a.steps)
        OUT.mkdir(exist_ok=True)
        cal.save(CAL)
        print(f"saved {CAL}")
    finally:
        cam.close()
        mount.disconnect()


def cmd_run(a):
    from dmk import Camera
    if not CAL.exists():
        sys.exit("no calibration yet: run `guide.py calibrate` first")
    mount, cam = connect(a.device, a.port), Camera(exposure_us=a.exposure)
    records = []
    try:
        records = guider.guide(mount, cam, guider.Calibration.load(CAL), target=a.target,
                               seconds=a.time, interval=a.interval, gain=a.gain)
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()
        mount.disconnect()
    if records:
        print(f"RMS error {guider.rms(records, skip=5):.2f} px over {len(records)} frames; log {save_log(records, 'guide')}")


def cmd_simulate(a):
    from simcam import SimCamera
    mount = connect("Telescope Simulator")
    try:
        mount.unpark()
        mount.set_tracking(True)
        here = mount.get_EOD_COORD()
        mount.move_coord(EOD_COORD(here.right_ascension, 30.0))
        cam = SimCamera(mount)
        scale = cam.scale

        print("== calibrating")
        cal = guider.calibrate(mount, cam)
        target = guider.locate(cam.frame())

        print(f"== unguided for {a.time:g} s (periodic error + drift only)")
        unguided = []
        start = time.monotonic()
        while time.monotonic() - start < a.time:
            err = np.subtract(guider.locate(cam.frame()), target)
            unguided.append((time.monotonic() - start, 0, 0, *err, 0, 0))
            time.sleep(1)
        print(f"   RMS {guider.rms(unguided):.2f} px = {guider.rms(unguided) * scale:.2f} arcsec")

        print(f"== guided for {a.time:g} s")
        records = guider.guide(mount, cam, cal, target=target, seconds=a.time, log=lambda s: None)
        r = guider.rms(records, skip=5)
        print(f"   RMS {r:.2f} px = {r * scale:.2f} arcsec (first 5 s skipped while it pulls the star back)")
        print(f"log {save_log(records, 'simulate')}")
    finally:
        mount.park(wait=False)
        mount.disconnect()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def hardware(s):
        s.add_argument("--device", default="iOptronV3", help="INDI device name")
        # /dev/mount: the udev rule from ansible/roles/hardware, on a node
        s.add_argument("--port", default="/dev/mount" if Path("/dev/mount").exists() else None,
                       help="mount serial port (default: /dev/mount, else the driver's)")
        s.add_argument("-e", "--exposure", type=int, default=100_000, help="guide exposure, us")

    s = sub.add_parser("calibrate", help="measure how guide pulses move the star")
    hardware(s)
    s.add_argument("--pulse", type=int, default=1000, help="pulse length, ms")
    s.add_argument("--steps", type=int, default=3, help="pulses per direction")
    s.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("run", help="guide until Ctrl-C (or --time)")
    hardware(s)
    s.add_argument("--target", type=float, nargs=2, metavar=("X", "Y"), help="pixel to hold the star on")
    s.add_argument("-t", "--time", type=float, help="seconds to guide (default: until Ctrl-C)")
    s.add_argument("--interval", type=float, default=1.0, help="seconds per correction")
    s.add_argument("--gain", type=float, default=0.7)
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("simulate", help="end-to-end test against indi_simulator_telescope")
    s.add_argument("-t", "--time", type=float, default=90, help="seconds unguided, then guided")
    s.set_defaults(fn=cmd_simulate)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
