import PyIndi
import sys
import asyncio
from loguru import logger
from typing import AsyncGenerator
from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration
from coordinate import EOD_COORD


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

    def on_coord_set(self):
        pass

    async def get_EOD_COORD(self):
        pass

    async def get_EOD_COORD_STREAM(self) -> AsyncGenerator[EOD_COORD, None]:
        pass

    class GenericMove:
        pass

    class CoordinateMove:
        pass
