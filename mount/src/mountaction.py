from enum import Enum


class MountMode(Enum):
    TRACK = "TRACK"
    SLEW = "SLEW"
    SYNC = "SYNC"

    @classmethod
    def Default(cls) -> "MountMode":
        return cls.SLEW  # slew by default
