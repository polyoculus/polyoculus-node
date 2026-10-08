import PyIndi
import threading
from loguru import logger
from mountConfiguration import MountConfiguration


class MountControlClient(PyIndi.BaseClient):
    """The client that connects to indiserver and communicates with the mount.

    Attributes:
        config: the mount configuration
    """

    config: MountConfiguration

    def __init__(self, config: MountConfiguration = MountConfiguration()):
        """Initializer for the Class"""
        self._device_event = threading.Event()
        self._property_events: dict[str, threading.Event] = {}
        self._connected_event = threading.Event()
        self.config = config
        self.connection_ready = threading.Event()
        self.mount_ready = threading.Event()

        self._required_props = {
            "EQUATORIAL_EOD_COORD",
            "TELESCOPE_PARK",
            "TELESCOPE_MOTION_NS",
            "TELESCOPE_MOTION_WE",
            "TELESCOPE_ABORT_MOTION",
            "TELESCOPE_TIMED_GUIDE_NS",
            "TELESCOPE_TIMED_GUIDE_WE",
            # any additional properties as needed
        }
        self._received_props = set()
        super().__init__()
        logger.info("new MountControlClient initialized!")

    def serverConnected(self):
        """informs when connected to indiserver"""
        logger.info("Connectd to INDI server")
        self._connected_event.set()

    def serverDisconnected(self, code):
        """informs when disconnected to indiserver

        Args:
            code (): an error code
        """
        logger.warning(f"Disconnected from INDI server, with code {code}")
        self._connected_event.clear()

    def newDevice(self, d):
        """informs when a new device is connected, and then releases a block

        Args:
            d (): the PyINDI device
        """
        name = d.getDeviceName()
        logger.info(f"New Device Connected: {name}")
        if name == self.config.DEVICE_NAME:
            self._device_event.set()

    def removeDevice(self, d):
        """informs when a device was removed

        Args:
            d (): the PyIINDI device
        """
        logger.warning(f"Device removed: {d.getDeviceName()}")

    def newProperty(self, p):
        """informs when a new property has been set

        Args:
            p (): the PyINDI property that was set
        """
        logger.debug(
            f"New Property: {p.getDeviceName()}.{p.getName()} ({p.getTypeAsString()})"
        )
        name = p.getName()
        device = p.getDeviceName()
        key = f"{device}.{name}"
        if key in self._property_events:
            self._property_events[key].set()

        if name == "CONNECTION":
            self.connection_ready.set()

        self._received_props.add(name)
        if self._required_props.issubset(self._received_props):
            self.mount_ready.set()

    def updateProperty(self, p):
        """informs when a property has been updated

        Args:
            p (): the PyINDI property that was updated
        """

        device = p.getDeviceName()
        name = p.getName()

        logger.debug(f"Updated: {device}.{name} ({p.getTypeAsString()})")
        key = f"{device}.{name}"
        if key in self._property_events:
            self._property_events[key].set()

    def removeProperty(self, p):
        """informs when a property has been removed

        Args:
            p (): the PyINDI property that was removed
        """
        logger.debug(f"Removed property: {p.getDeviceName()}.{p.getName()}")

    def newMessage(self, d, m):
        """informs when a new message was recieved from indiserver

        Args:
            d (): the device for the message
            m (): the message
        """
        logger.info(f"Message [{d.getDeviceName()}: {d.messageQueue(m)}")

    def wait_for_device(self):
        """blocks the thread and waits for a device to connect, for the TIMEOUT amount of time

        Raises:
            TimeoutError: a TimeoutError caused when the wait time is too long
        """
        if not self._device_event.wait(self.config.TIMEOUT):
            raise TimeoutError(
                f"Device '{self.config.DEVICE_NAME}' did not appear within {self.config.TIMEOUT}s"
            )

    def wait_for_property(self, prop_name):
        """blocks the thread and waits for a property, for the TIMEOUT amount of time

        Args:
            prop_name (): the property name

        Raises:
            TimeoutError: a TimeoutError caused when the wait time is too long
        """
        key = f"{self.config.DEVICE_NAME}.{prop_name}"
        if key not in self._property_events:
            self._property_events[key] = threading.Event()

        dev = self.getDevice(self.config.DEVICE_NAME)
        if dev:
            prop = dev.getProperty(prop_name)
            if prop:
                self._property_events[key].set()
                return
        if not self._property_events[key].wait(self.config.TIMEOUT):
            raise TimeoutError(
                f"Property '{prop_name}' on '{self.config.DEVICE_NAME}' not received within {self.config.TIMEOUT}s"
            )
