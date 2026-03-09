from loguru import logger
from MountOperator import MountOperator
from cardinalDirection import CardinalDirection


def main():
    logger.info("Hello iOptron!")
    operator = MountOperator()

    operator.connect()

    operator.move_dir(direction=CardinalDirection.North, timeout=8)
    operator.move_dir(direction=CardinalDirection.West, timeout=8)
    operator.move_dir(direction=CardinalDirection.South, timeout=5)
    operator.move_dir(direction=CardinalDirection.East, timeout=5)

    operator.go_home()


if __name__ == "__main__":
    logger.info("package currently being run in Demo mode")
    main()
