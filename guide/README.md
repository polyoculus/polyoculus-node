# guide

Slow autoguiding for a telescope node: the DMK guide camera (`../camera`) watches the star,
and guide pulses to the mount (`../mount`) hold it on a target pixel, e.g. the fiber.

    uv run guide.py calibrate                # once per night, or after the camera moves
    uv run guide.py run                      # hold the star where it is now (Ctrl-C to stop)
    uv run guide.py run --target 712 540     # hold it on a pixel
    uv run guide.py simulate                 # end-to-end test, no hardware

`indiserver indi_ioptronv3_telescope` must be running first; on a node it runs at boot
(`indiserver.service`). `simulate` needs `indi_simulator_telescope` on the same port, so stop the
service first there. The mount port defaults to `/dev/mount` when it exists. Logs and the
calibration go to `captures/`.

## How it works

- **Finding the star:** brightest spot on a 2x2-binned frame (so a hot pixel can't win), then
  `fsm.centroid` in a 40 px window. After the first frame only the window is searched.
- **Calibration:** pulse west, then north, measure how far the star moves, and undo each move.
  That gives pixels per millisecond for each axis, whatever the camera's rotation.
- **Each cycle** (1 s by default): pixel error -> pulse lengths through the calibration,
  times a gain of 0.7 so noise isn't chased; errors under 0.15 px are ignored, and pulses are
  capped at 80% of the cycle.

## Simulated performance (2026-10-08)

`simulate` renders the star where the INDI telescope simulator points, adding 5" periodic error
(120 s period) and drift, at the C11's 0.254"/px:

| | RMS |
|---|---|
| unguided | 3.01" (11.8 px) |
| guided, 1 s cycle | 0.29" (1.1 px) |

## Tests

    uv run pytest
