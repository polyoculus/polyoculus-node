from enum import Enum


class CardinalDirection(Enum):
    """Encodes both the INDI property name and switch name for each direction.

    Each value is a (prop_name, switch_name) tuple corresponding to the INDI
    properties used to command mount motion.
    """

    North = ("TELESCOPE_MOTION_NS", "MOTION_NORTH")
    South = ("TELESCOPE_MOTION_NS", "MOTION_SOUTH")
    West = ("TELESCOPE_MOTION_WE", "MOTION_WEST")
    East = ("TELESCOPE_MOTION_WE", "MOTION_EAST")

    @property
    def prop_name(self) -> str:
        return self.value[0]

    @property
    def switch_name(self) -> str:
        return self.value[1]
