from loguru import logger
from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration


def main():
    logger.info("hello iOptron!")
    logger.info("now attempting to connect to indiserver")

    client = MountControlClient()
    config = MountConfiguration()
    device = None

    client.connectServer()

    client.wait_for_device()
    device = client.getDevice(config.DEVICE_NAME)

    # currently, the demo section is incomplete. We can connect to indiserver, and get the device info, but that is all


if __name__ == "__main__":
    logger.info("package currently being run in Demo mode")
    main()
