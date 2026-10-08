import numpy as np
import pytest

import guider
from cardinalDirection import CardinalDirection as D

H, W = 1080, 1440
yy, xx = np.mgrid[0:H, 0:W]


def frame(x, y, hot=True):
    img = 240 + np.random.default_rng(0).normal(0, 2, (H, W))
    img += 2000 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 2.5 ** 2))
    if hot:
        img[100, 200] = 4000  # brighter than the star's peak pixel
    return np.clip(img, 0, 4094).astype(np.uint16)


def test_find_star_ignores_hot_pixel():
    x, y = guider.find_star(frame(812.3, 431.7))
    assert abs(x - 812.3) < 0.1 and abs(y - 431.7) < 0.1


def test_locate_falls_back_when_star_left_window():
    x, y = guider.locate(frame(300.0, 900.0), last=(1000, 200))
    assert abs(x - 300) < 0.1 and abs(y - 900) < 0.1


def test_pulses_undo_the_error():
    cal = guider.Calibration(west=(0.03, 0.01), north=(-0.008, 0.028))
    err = np.array([4.0, -2.5])
    west_ms, north_ms = cal.pulses(err)
    moved = west_ms * np.array(cal.west) + north_ms * np.array(cal.north)
    assert np.allclose(moved, -err)


def test_angle_between_axes():
    assert guider.Calibration(west=(1, 0), north=(0, 2)).angle_deg() == pytest.approx(90)


def test_save_load_roundtrip(tmp_path):
    cal = guider.Calibration(west=(0.03, 0.01), north=(-0.008, 0.028))
    cal.save(tmp_path / "cal.json")
    assert guider.Calibration.load(tmp_path / "cal.json") == cal


class FakeRig:
    """Mount + camera in one: pulses move the star through a fixed matrix; it also drifts."""

    def __init__(self):
        self.west, self.north = np.array([0.03, 0.012]), np.array([-0.01, 0.029])  # px per ms
        self.pos = np.array([700.0, 500.0])
        self.drift = np.array([0.4, -0.25])  # px per frame

    def guide(self, direction, ms, wait=True):
        sign = {D.West: (1, 0), D.East: (-1, 0), D.North: (0, 1), D.South: (0, -1)}[direction]
        self.pos += ms * (sign[0] * self.west + sign[1] * self.north)

    def frame(self):
        self.pos += self.drift
        return frame(*self.pos, hot=False)


def test_calibrate_recovers_the_matrix():
    rig = FakeRig()
    rig.drift[:] = 0
    cal = guider.calibrate(rig, rig, pulse_ms=500, steps=2, settle=0, log=lambda s: None)
    assert np.allclose(cal.west, rig.west, atol=1e-3) and np.allclose(cal.north, rig.north, atol=1e-3)


def test_guide_holds_star_against_drift():
    rig = FakeRig()
    cal = guider.Calibration(west=tuple(rig.west), north=tuple(rig.north))
    records = guider.guide(rig, rig, cal, target=(700, 500), seconds=1.0, interval=0.02,
                           max_ms=1000, log=lambda s: None)
    # unguided the star would walk ~0.5 px per frame; guided it stays within about a frame's drift
    assert len(records) > 10
    assert guider.rms(records, skip=3) < 1.0
