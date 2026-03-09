import PyIndi
import sys
import time
from loguru import logger
from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD
from mountaction import MountMode
from cardinalDirection import CardinalDirection


class MountOperator:
    client: MountControlClient
    config: MountConfiguration
    device: PyIndi.PyIndi.BaseDevice

    def __init__(
        self,
        client: MountControlClient = MountControlClient(),
        config: MountConfiguration = MountConfiguration(),
        device: PyIndi.PyIndi.BaseDevice = None,
    ):
        self.client = client
        self.config = config
        self.device = device

        logger.info("Instance of MountOperator initialized! Hello!")

    def connect(self):
        logger.debug("Attempting to connect to mount now...")
        self.client.connectServer()
        self.client.wait_for_device()  # wait for device to appear
        self.device = self.client.getDevice(self.config.DEVICE_NAME)

        # wait for the device to connect
        if not self.client.connection_ready.wait(timeout=self.config.TIMEOUT):
            logger.fault("Timed out while waiting for connection property to appear.")
            sys.exit(
                1
            )  # we are using exit for now. Implement better error handling later

        # now, connect to the device
        conn_prop = self.device.getProperty("CONNECTION")
        conn_sp = PyIndi.PropertySwitch(conn_prop)
        for sw in conn_sp:
            if sw.getName() == "CONNECT":
                sw.setState(PyIndi.ISS_ON)
            else:
                sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(conn_sp)

        if not self.client.mount_ready.wait(timeout=self.config.TIMEOUT):
            logger.fault(
                "Timed out while waiting for the necessary mount properties to arrive."
            )
            sys.exit(2)  # another sys.exit. change later

        logger.info("Connection to Mount successful!")

    def disconnect(self):
        pass

    def on_coord_set_mode(self, mode: MountMode = MountMode.Default()):
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
        logger.info("Going home now!")
        prop = self.device.getProperty("TELESCOPE_HOME")
        sp = PyIndi.PropertySwitch(prop)

        for sw in sp:
            if sw.getName() == "GO":
                sw.setState(PyIndi.ISS_ON)
            else:
                sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)

    def set_slew_speed(self, speed: int):
        pass

    def move_dir(
        self, direction: CardinalDirection = CardinalDirection.North, timeout: int = 120
    ):
        prop_name = None
        on_name = None
        match direction:
            case CardinalDirection.North:
                prop_name = "TELESCOPE_MOTION_NS"
                on_name = "MOTION_NORTH"
            case CardinalDirection.South:
                prop_name = "TELESCOPE_MOTION_NS"
                on_name = "MOTION_SOUTH"
            case CardinalDirection.West:
                prop_name = "TELESCOPE_MOTION_WE"
                on_name = "MOTION_WEST"
            case CardinalDirection.East:
                prop_name = "TELESCOPE_MOTION_WE"
                on_name = "MOTION_EAST"

        prop = self.device.getProperty(prop_name)
        sp = PyIndi.PropertySwitch(prop)

        logger.info(f"Moving in the {direction} direction for {timeout}s")
        for sw in sp:
            if sw.getName() == on_name:
                sw.setState(PyIndi.ISS_ON)
            else:
                sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)
        time.sleep(timeout)
        for sw in sp:
            sw.setState(PyIndi.ISS_OFF)
        self.client.sendNewSwitch(sp)
