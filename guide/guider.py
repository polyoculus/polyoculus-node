"""Slow autoguiding: keep a star on a target pixel by sending guide pulses to the mount.

Works with anything that has `frame()` (camera) and `guide(direction, ms, wait)` (mount):
camera/dmk.py's Camera and mount/'s MountOperator, or the simulator in simcam.py.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from cardinalDirection import CardinalDirection
from fsm import centroid


def find_star(img, r=40):
    """Brightest spot on a 2x2-binned frame (a lone hot pixel can't win), then a window centroid."""
    h, w = img.shape
    binned = img[: h // 2 * 2, : w // 2 * 2].reshape(h // 2, 2, w // 2, 2).sum((1, 3), dtype=np.uint32)
    y, x = divmod(int(binned.argmax()), binned.shape[1])
    return centroid(img, (2 * x + 1, 2 * y + 1, r))


def locate(img, last=None, r=40):
    """Star position: a window around the last one if given, else (or if it left the window) the whole frame."""
    c = centroid(img, (*last, r)) if last is not None else None
    return c or find_star(img, r)


@dataclass
class Calibration:
    """How the star moves on the sensor per millisecond of guide pulse (pixels/ms)."""

    west: tuple[float, float]
    north: tuple[float, float]

    def pulses(self, error):
        """Pulse lengths (west_ms, north_ms) that move the star by -error; negative means east / south."""
        m = np.column_stack([self.west, self.north])
        return -np.linalg.solve(m, np.asarray(error, float))

    def angle_deg(self):
        """Angle between the RA and Dec directions on the sensor; ~90 if calibration is sane."""
        w, n = np.asarray(self.west), np.asarray(self.north)
        return float(np.degrees(np.arccos(abs(w @ n) / (np.linalg.norm(w) * np.linalg.norm(n)))))

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path):
        return cls(**{k: tuple(v) for k, v in json.loads(Path(path).read_text()).items()})


def calibrate(mount, camera, pulse_ms=1000, steps=3, settle=1.5, log=print):
    """Pulse west then north, measure how far the star moves, and undo each move.

    Needs the star to move a few tens of pixels; raise pulse_ms or steps if it doesn't.
    """
    def measure(last=None):
        time.sleep(settle)
        p = locate(camera.frame(), last)
        if p is None:
            raise RuntimeError("no star found during calibration")
        return np.array(p)

    def push(direction):
        for _ in range(steps):
            mount.guide(direction, pulse_ms)

    total = pulse_ms * steps
    p0 = measure()
    push(CardinalDirection.West)
    p1 = measure(p0)
    push(CardinalDirection.East)
    p2 = measure(p1)
    push(CardinalDirection.North)
    p3 = measure(p2)
    push(CardinalDirection.South)

    cal = Calibration(west=tuple((p1 - p0) / total), north=tuple((p3 - p2) / total))
    moved = min(np.hypot(*(p1 - p0)), np.hypot(*(p3 - p2)))
    log(f"calibration: west {np.hypot(*cal.west) * 1000:.1f} px/s, north {np.hypot(*cal.north) * 1000:.1f} px/s, "
        f"axes {cal.angle_deg():.1f}° apart")
    if moved < 5:
        raise RuntimeError(f"star only moved {moved:.1f} px; increase pulse_ms or steps")
    if not 70 < cal.angle_deg() < 110:
        log("warning: RA and Dec axes are far from perpendicular; check for backlash or a bad star")
    return cal


def guide(mount, camera, cal, target=None, seconds=None, interval=1.0, gain=0.7,
          min_px=0.15, max_ms=None, log=print):
    """Hold the star on `target` (pixel x, y; default: where it is now). Returns the per-frame records.

    Each cycle: find the star, turn its pixel error into west/north pulse lengths through the
    calibration, apply `gain` (<1 so noise isn't chased), skip errors under `min_px`, and cap
    pulses at `max_ms` (default 80% of the interval so a pulse ends before the next frame).
    """
    max_ms = max_ms or 0.8 * interval * 1000
    pos = locate(camera.frame())
    if pos is None:
        raise RuntimeError("no star in the frame")
    target = np.asarray(target if target is not None else pos, float)
    log(f"guiding on ({target[0]:.1f}, {target[1]:.1f}), {interval:g} s cycle")

    records, start = [], time.monotonic()
    while seconds is None or time.monotonic() - start < seconds:
        t0 = time.monotonic()
        pos = locate(camera.frame(), pos)
        if pos is None:
            log("lost the star; holding")
            time.sleep(interval)
            continue
        err = np.asarray(pos) - target
        west_ms = north_ms = 0.0
        if np.hypot(*err) >= min_px:
            west_ms, north_ms = np.clip(gain * cal.pulses(err), -max_ms, max_ms)
            mount.guide(CardinalDirection.West if west_ms > 0 else CardinalDirection.East, round(abs(west_ms)), wait=False)
            mount.guide(CardinalDirection.North if north_ms > 0 else CardinalDirection.South, round(abs(north_ms)), wait=False)
        records.append((t0 - start, *pos, *err, west_ms, north_ms))
        log(f"{t0 - start:6.1f}s  err {err[0]:+6.2f} {err[1]:+6.2f} px   pulse W{west_ms:+5.0f} N{north_ms:+5.0f} ms")
        time.sleep(max(0.0, interval - (time.monotonic() - t0)))
    return records


def rms(records, skip=0):
    """RMS of the total pixel error over the records (optionally skipping the first `skip`)."""
    e = np.array([r[3:5] for r in records[skip:]])
    return float(np.sqrt((e ** 2).sum(1).mean())) if len(e) else float("nan")
