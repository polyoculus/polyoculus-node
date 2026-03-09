from dataclasses import dataclass


@dataclass
class MountConfiguration:
    """Configuration details for MountControlClient in connecting to indiserver

    Attributes:
        INDI_HOST: The hostname of where the server is. Default is "localhost"
        INDI_PORT: The port of where the server is. Default is 7624, which is the default set by indiserver.
        DEVICE_NAME: The device name as specified by the indi driver. Default, for our iOptron mount, is "iOptronV3". Note, this is case sensitive
        BAUD_RATE: The baud rate for the driver to use. Default is "115200". Note, that this is the highest supported baud rate for the iOptron mounts.
        TIMEOUT: The timeout delay, in seconds. Default is 30 seconds, but if this is too long, please modify.
    """

    INDI_HOST: str
    INDI_PORT: int
    DEVICE_NAME: str
    BAUD_RATE: str
    TIMEOUT = int

    def __init__(
        self,
        INDI_HOST: str = "localhost",
        INDI_PORT: int = 7624,
        DEVICE_NAME: str = "iOptronV3",
        BAUD_RATE: str = "115200",
        TIMEOUT: int = 30,
    ):
        self.INDI_HOST = INDI_HOST
        self.INDI_PORT = INDI_PORT
        self.DEVICE_NAME = DEVICE_NAME
        self.BAUD_RATE = BAUD_RATE
        self.TIMEOUT = TIMEOUT
