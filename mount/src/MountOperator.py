import threading

import PyIndi
from loguru import logger

from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD
from mountaction import MountMode
from cardinalDirection import CardinalDirection
from exceptions import MountConnectionError, MountTimeoutError


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

        conn_prop = self.device.getProperty("CONNECTION")
        conn_sp = PyIndi.PropertySwitch(conn_prop)
        for sw in conn_sp:
            sw.setState(PyIndi.ISS_ON if sw.getName() == "CONNECT" else PyIndi.ISS_OFF)
        self.client.sendNewSwitch(conn_sp)

        if not self.client.mount_ready.wait(timeout=self.config.TIMEOUT):
            raise MountTimeoutError(
                "Timed out waiting for required mount properties to arrive."
            )

        logger.info("Connected to mount successfully.")

    def disconnect(self):
        pass

    def on_coord_set_mode(self, mode: MountMode = MountMode.Default()):
        """Set the ON_COORD_SET mode (SLEW, TRACK, or SYNC)."""
        props = self.device.getSwitch("ON_COORD_SET")
        match mode:
            case MountMode.SLEW:
                props[0].setState(PyIndi.ISS_ON)
                props[1].setState(PyIndi.ISS_OFF)
                props[2].setState(PyIndi.ISS_OFF)
            case MountMode.TRACK:
                props[0].setState(PyIndi.ISS_OFF)
                props[1].setState(PyIndi.ISS_ON)
                props[2].setState(PyIndi.ISS_OFF)
            case MountMode.SYNC:
                props[0].setState(PyIndi.ISS_OFF)
                props[1].setState(PyIndi.ISS_OFF)
                props[2].setState(PyIndi.ISS_ON)
        self.client.sendNewSwitch(props)

    def get_EOD_COORD(self) -> EOD_COORD:
        pass

    def go_home(self):
        """Send the mount to its home position."""
        logger.info("Going home.")
        prop = self.device.getProperty("TELESCOPE_HOME")
        sp = PyIndi.PropertySwitch(prop)
        for sw in sp:
            sw.setState(PyIndi.ISS_ON if sw.getName() == "GO" else PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def park(self):
        pass

    def unpark(self):
        pass

    def set_slew_speed(self, speed: int):
        pass

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

    def move_coord(self, coordinate: EOD_COORD):
        pass

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
