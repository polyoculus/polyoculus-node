import threading
import time

import PyIndi
from loguru import logger

from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD
from mountaction import MountMode
from cardinalDirection import CardinalDirection
from exceptions import MountConnectionError, MountError, MountTimeoutError


class MountOperator:
    """High-level interface for controlling a telescope mount via INDI.

    Attributes:
        client: The MountControlClient used to communicate with indiserver.
        config: The MountConfiguration (host, port, device name, timeouts, etc.).
        device: The PyIndi BaseDevice once connected.
    """

    client: MountControlClient
    config: MountConfiguration
    device: PyIndi.PyIndi.BaseDevice

    def __init__(
        self,
        client: MountControlClient = None,
        config: MountConfiguration = None,
    ):
        self.config = config or MountConfiguration()
        self.client = client or MountControlClient(self.config)
        self.device = None
        self._abort_event = threading.Event()

        logger.info("MountOperator initialized.")

    def connect(self):
        """Connect to indiserver and wait for the mount device and its properties."""
        logger.debug("Connecting to mount...")
        self.client.connectServer()
        self.client.wait_for_device()

        self.device = self.client.getDevice(self.config.DEVICE_NAME)

        if not self.client.connection_ready.wait(timeout=self.config.TIMEOUT):
            raise MountTimeoutError(
                "Timed out waiting for the CONNECTION property to appear."
            )

        # serial settings must be in place before CONNECT; simulators have neither property
        if self.config.DEVICE_PORT and self.device.getProperty("DEVICE_PORT").isValid():
            tp = PyIndi.PropertyText(self.device.getProperty("DEVICE_PORT"))
            tp[0].setText(self.config.DEVICE_PORT)
            self.client.sendNewText(tp)
        if self.device.getProperty("DEVICE_BAUD_RATE").isValid():
            self._switch("DEVICE_BAUD_RATE", self.config.BAUD_RATE)

        self._switch("CONNECTION", "CONNECT")

        if not self.client.mount_ready.wait(timeout=self.config.TIMEOUT):
            raise MountTimeoutError(
                "Timed out waiting for required mount properties to arrive."
            )

        logger.info("Connected to mount successfully.")

    def disconnect(self):
        """Disconnect the mount driver and drop the indiserver connection."""
        if self.device is not None:
            self._switch("CONNECTION", "DISCONNECT")
        self.client.disconnectServer()
        logger.info("Disconnected from mount.")

    def _switch(self, prop_name: str, on: str):
        """Turn on the switch named `on` in a switch property, turn the others off, and send it."""
        sp = PyIndi.PropertySwitch(self.device.getProperty(prop_name))
        for sw in sp:
            sw.setState(PyIndi.ISS_ON if sw.getName() == on else PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def _wait_done(self, prop_name: str, timeout: float):
        """Block until a property stops being BUSY; raise if it ends in ALERT or never finishes."""
        deadline = time.monotonic() + timeout
        time.sleep(0.2)  # let the driver flip the state to BUSY first
        while time.monotonic() < deadline:
            state = self.device.getProperty(prop_name).getState()
            if state == PyIndi.IPS_ALERT:
                raise MountError(f"{prop_name} failed (ALERT)")
            if state != PyIndi.IPS_BUSY:
                return
            time.sleep(0.2)
        raise MountTimeoutError(f"{prop_name} still busy after {timeout}s")

    def on_coord_set_mode(self, mode: MountMode = MountMode.Default()):
        """Set what the mount does with the next coordinates: SLEW, TRACK (slew then track), or SYNC.

        Switches are picked by name: INDI orders them TRACK, SLEW, SYNC, not SLEW, TRACK, SYNC.
        """
        self._switch("ON_COORD_SET", mode.value)

    def get_EOD_COORD(self) -> EOD_COORD:
        """Current pointing: RA in hours and Dec in degrees, both of date (JNow)."""
        np_ = PyIndi.PropertyNumber(self.device.getProperty("EQUATORIAL_EOD_COORD"))
        values = {n.getName(): n.getValue() for n in np_}
        return EOD_COORD(values["RA"], values["DEC"])

    def go_home(self):
        """Send the mount to its home position."""
        logger.info("Going home.")
        prop = self.device.getProperty("TELESCOPE_HOME")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_ON if sw.getName() == "GO" else PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def park(self, wait: bool = True):
        """Park the mount (and stop tracking)."""
        logger.info("Parking.")
        self._switch("TELESCOPE_PARK", "PARK")
        if wait:
            self._wait_done("TELESCOPE_PARK", self.config.SLEW_TIMEOUT)

    def unpark(self, wait: bool = True):
        """Unpark the mount so it accepts motion commands."""
        logger.info("Unparking.")
        self._switch("TELESCOPE_PARK", "UNPARK")
        if wait:
            self._wait_done("TELESCOPE_PARK", self.config.TIMEOUT)

    def set_slew_speed(self, speed: int):
        """Set the manual slew rate used by move_dir: 1 is the slowest the driver offers.

        Drivers name their rates differently (the simulator has 1x..4x, iOptron has more),
        so this picks by position.
        """
        sp = PyIndi.PropertySwitch(self.device.getProperty("TELESCOPE_SLEW_RATE"))
        names = [sw.getName() for sw in sp]
        if not 1 <= speed <= len(names):
            raise ValueError(f"speed must be 1..{len(names)} ({', '.join(names)})")
        self._switch("TELESCOPE_SLEW_RATE", names[speed - 1])

    def set_tracking(self, on: bool = True):
        """Turn sidereal tracking on or off."""
        self._switch("TELESCOPE_TRACK_STATE", "TRACK_ON" if on else "TRACK_OFF")

    _GUIDE = {
        CardinalDirection.North: ("TELESCOPE_TIMED_GUIDE_NS", "TIMED_GUIDE_N"),
        CardinalDirection.South: ("TELESCOPE_TIMED_GUIDE_NS", "TIMED_GUIDE_S"),
        CardinalDirection.West: ("TELESCOPE_TIMED_GUIDE_WE", "TIMED_GUIDE_W"),
        CardinalDirection.East: ("TELESCOPE_TIMED_GUIDE_WE", "TIMED_GUIDE_E"),
    }

    def guide(self, direction: CardinalDirection, ms: int, wait: bool = True):
        """Send a guide pulse: move at the guide rate (a fraction of sidereal) for `ms` milliseconds."""
        if ms <= 0:
            return
        prop_name, element = self._GUIDE[direction]
        np_ = PyIndi.PropertyNumber(self.device.getProperty(prop_name))
        for n in np_:
            n.setValue(ms if n.getName() == element else 0)
        self.client.sendNewNumber(np_)
        if wait:
            self._wait_done(prop_name, ms / 1000 + self.config.TIMEOUT)

    def move_dir(
        self, direction: CardinalDirection = CardinalDirection.North, timeout: int = 120
    ):
        """Move the mount in a cardinal direction for a given number of seconds.

        The move can be interrupted early by calling move_abort_on() or
        move_emergency_abort() from another thread.

        Args:
            direction: The direction to move (North, South, East, West).
            timeout: How long to move in seconds.
        """
        prop = self.device.getProperty(direction.prop_name)
        sp = PyIndi.PropertySwitch(prop)

        logger.info(f"Moving {direction.name} for {timeout}s.")
        for sw in sp:
            sw.setState(
                PyIndi.ISS_ON if sw.getName() == direction.switch_name else PyIndi.ISS_OFF
            )
        self.client.sendNewSwitch(sp)

        self._abort_event.clear()
        self._abort_event.wait(timeout=timeout)

        for sw in sp:
            sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def move_coord(self, coordinate: EOD_COORD, mode: MountMode = MountMode.TRACK, wait: bool = True):
        """Point at RA (hours) / Dec (degrees), of date.

        TRACK (the default) slews and then tracks the target; SLEW stops after arriving;
        SYNC tells the mount it is already pointing there (after a plate solve).
        """
        logger.info(f"{mode.value} to RA {coordinate.right_ascension:.4f}h Dec {coordinate.declination:+.4f}°")
        self.on_coord_set_mode(mode)
        np_ = PyIndi.PropertyNumber(self.device.getProperty("EQUATORIAL_EOD_COORD"))
        for n in np_:
            n.setValue(coordinate.right_ascension if n.getName() == "RA" else coordinate.declination)
        self.client.sendNewNumber(np_)
        if wait:
            self._wait_done("EQUATORIAL_EOD_COORD", self.config.SLEW_TIMEOUT)

    def move_abort_on(self):
        """Halt all mount movement gracefully via TELESCOPE_ABORT_MOTION."""
        logger.info("Aborting motion.")
        self._abort_event.set()
        prop = self.device.getProperty("TELESCOPE_ABORT_MOTION")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_ON)
        self.client.sendNewSwitch(sp)

    def move_abort_off(self):
        """Clear the TELESCOPE_ABORT_MOTION switch."""
        prop = self.device.getProperty("TELESCOPE_ABORT_MOTION")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def move_emergency_abort(self):
        """Halt all mount movement as fast as possible by zeroing motion switches directly."""
        logger.warning("Emergency abort!")
        self._abort_event.set()
        prop = self.device.getProperty("TELESCOPE_MOTION_NS")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

        prop = self.device.getProperty("TELESCOPE_MOTION_WE")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)
