"""A fake guide camera for testing against the INDI telescope simulator.

Renders one star at the position the simulated mount's pointing implies, plus the tracking
errors a real mount has: periodic error from the RA worm gear and slow drift (polar
misalignment). Guide pulses move the simulated mount, which moves the star, so the guider
is tested end to end without hardware.
"""

import time

import numpy as np

HEIGHT, WIDTH = 1080, 1440


class SimCamera:
    def __init__(self, mount, scale=0.254, angle_deg=25.0, pe_arcsec=5.0, pe_period=120.0,
                 drift=(0.03, 0.02), seed=0):
        """scale: arcsec/pixel (C11 at f/10 with 3.45 um pixels is 0.254).
        angle_deg: camera rotation vs. the RA/Dec axes. pe_*: periodic error amplitude and
        period. drift: (RA, Dec) arcsec per second."""
        self.mount, self.scale = mount, scale
        a = np.radians(angle_deg)
        self.rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        self.pe, self.pe_period, self.drift = pe_arcsec, pe_period, np.array(drift)
        self.rng = np.random.default_rng(seed)
        self.ref = mount.get_EOD_COORD()
        self.t0 = time.monotonic()
        self.yy, self.xx = np.mgrid[0:64, 0:64]

    def sky_offset(self):
        """Where the star sits relative to its starting point, in arcsec (RA, Dec)."""
        c, t = self.mount.get_EOD_COORD(), time.monotonic() - self.t0
        ra = (c.right_ascension - self.ref.right_ascension) * 15 * 3600 * np.cos(np.radians(c.declination))
        dec = (c.declination - self.ref.declination) * 3600
        tracking = np.array([self.pe * np.sin(2 * np.pi * t / self.pe_period), 0.0]) + self.drift * t
        return np.array([ra, dec]) + tracking

    def star_xy(self):
        return np.array([WIDTH / 2, HEIGHT / 2]) + self.rot @ (self.sky_offset() / self.scale)

    def frame(self):
        img = 240 + self.rng.normal(0, 2, (HEIGHT, WIDTH))
        x, y = self.star_xy()
        x0, y0 = int(x) - 32, int(y) - 32
        if 0 <= x0 < WIDTH - 64 and 0 <= y0 < HEIGHT - 64:
            img[y0:y0 + 64, x0:x0 + 64] += 2000 * np.exp(
                -((self.xx + x0 - x) ** 2 + (self.yy + y0 - y) ** 2) / (2 * 2.5 ** 2))
        img[100, 200] = 4000  # a hot pixel, which find_star must ignore
        return np.clip(img, 0, 4094).astype(np.uint16)
