from dataclasses import dataclass, field


@dataclass
class MountConfiguration:
    """Configuration for connecting to indiserver and the mount device.

    Attributes:
        INDI_HOST: Hostname of the indiserver. Default is "localhost".
        INDI_PORT: Port of the indiserver. Default is 7624.
        DEVICE_NAME: INDI driver device name. Default is "iOptronV3" (case-sensitive).
        BAUD_RATE: Baud rate for the serial connection. Default is "115200".
        DEVICE_PORT: Serial port of the mount, e.g. "/dev/ttyUSB0". None keeps the driver's default.
        TIMEOUT: Timeout in seconds for connection/property waits. Default is 30.
        SLEW_TIMEOUT: Timeout in seconds for a slew or park to finish. Default is 180.
    """

    INDI_HOST: str = "localhost"
    INDI_PORT: int = 7624
    DEVICE_NAME: str = "iOptronV3"
    BAUD_RATE: str = "115200"
    DEVICE_PORT: str | None = None
    TIMEOUT: int = 30
    SLEW_TIMEOUT: int = 180
