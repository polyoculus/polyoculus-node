"""Unit tests for data classes, enums, and helpers (no hardware required)."""

import sys
import pytest

# conftest.py stubs PyIndi before any imports happen


class TestMountConfiguration:
    def test_defaults(self):
        from mountConfiguration import MountConfiguration
        c = MountConfiguration()
        assert c.INDI_HOST == "localhost"
        assert c.INDI_PORT == 7624
        assert c.DEVICE_NAME == "iOptronV3"
        assert c.BAUD_RATE == "115200"
        assert c.TIMEOUT == 30

    def test_custom_values(self):
        from mountConfiguration import MountConfiguration
        c = MountConfiguration(INDI_HOST="192.168.1.10", INDI_PORT=9999, TIMEOUT=60)
        assert c.INDI_HOST == "192.168.1.10"
        assert c.INDI_PORT == 9999
        assert c.TIMEOUT == 60

    def test_timeout_is_int(self):
        from mountConfiguration import MountConfiguration
        c = MountConfiguration()
        assert isinstance(c.TIMEOUT, int)


class TestCardinalDirection:
    def test_prop_names(self):
        from cardinalDirection import CardinalDirection
        assert CardinalDirection.North.prop_name == "TELESCOPE_MOTION_NS"
        assert CardinalDirection.South.prop_name == "TELESCOPE_MOTION_NS"
        assert CardinalDirection.East.prop_name == "TELESCOPE_MOTION_WE"
        assert CardinalDirection.West.prop_name == "TELESCOPE_MOTION_WE"

    def test_switch_names(self):
        from cardinalDirection import CardinalDirection
        assert CardinalDirection.North.switch_name == "MOTION_NORTH"
        assert CardinalDirection.South.switch_name == "MOTION_SOUTH"
        assert CardinalDirection.East.switch_name == "MOTION_EAST"
        assert CardinalDirection.West.switch_name == "MOTION_WEST"

    def test_all_directions_present(self):
        from cardinalDirection import CardinalDirection
        directions = {d.name for d in CardinalDirection}
        assert directions == {"North", "South", "East", "West"}


class TestMountMode:
    def test_default_is_slew(self):
        from mountaction import MountMode
        assert MountMode.Default() == MountMode.SLEW

    def test_values(self):
        from mountaction import MountMode
        assert MountMode.SLEW.value == "SLEW"
        assert MountMode.TRACK.value == "TRACK"
        assert MountMode.SYNC.value == "SYNC"


class TestEODCoord:
    def test_fields(self):
        from coordinate import EOD_COORD
        c = EOD_COORD(right_ascension=12.5, declination=-30.0)
        assert c.right_ascension == 12.5
        assert c.declination == -30.0

    def test_immutable(self):
        from coordinate import EOD_COORD
        c = EOD_COORD(1.0, 2.0)
        with pytest.raises(AttributeError):
            c.right_ascension = 5.0


class TestHelpers:
    def test_state_str_known(self):
        import PyIndi
        from helpers import Helpers
        assert Helpers.state_str(PyIndi.IPS_IDLE) == "Idle"
        assert Helpers.state_str(PyIndi.IPS_OK) == "OK"
        assert Helpers.state_str(PyIndi.IPS_BUSY) == "Busy"
        assert Helpers.state_str(PyIndi.IPS_ALERT) == "Alert"

    def test_state_str_unknown(self):
        from helpers import Helpers
        result = Helpers.state_str(999)
        assert "Unknown" in result

    def test_switch_str(self):
        import PyIndi
        from helpers import Helpers
        assert Helpers.switch_str(PyIndi.ISS_ON) == "ON"
        assert Helpers.switch_str(PyIndi.ISS_OFF) == "OFF"


class TestExceptions:
    def test_hierarchy(self):
        from exceptions import MountError, MountConnectionError, MountTimeoutError
        assert issubclass(MountConnectionError, MountError)
        assert issubclass(MountTimeoutError, MountConnectionError)
        assert issubclass(MountTimeoutError, MountError)

    def test_raise_mount_error(self):
        from exceptions import MountError
        with pytest.raises(MountError):
            raise MountError("test")

    def test_raise_timeout_caught_as_connection_error(self):
        from exceptions import MountConnectionError, MountTimeoutError
        with pytest.raises(MountConnectionError):
            raise MountTimeoutError("timed out")
