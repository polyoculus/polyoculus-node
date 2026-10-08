"""Tests for MountOperator with mocked INDI client and device."""

import threading
from unittest.mock import MagicMock
import time
import pytest

# conftest.py stubs PyIndi before any imports happen


class TestConnect:
    def test_connect_success(self, operator, mock_client, mock_device):
        """connect() should call connectServer, wait_for_device, and sendNewSwitch."""
        operator.connect()
        mock_client.connectServer.assert_called_once()
        mock_client.wait_for_device.assert_called_once()
        mock_client.sendNewSwitch.assert_called()

    def test_connect_timeout_on_connection_ready(self, config, mock_client):
        """connect() raises MountTimeoutError if connection_ready times out."""
        import importlib
        import MountOperator as mo_module
        importlib.reload(mo_module)
        from MountOperator import MountOperator
        from exceptions import MountTimeoutError

        mock_client.connection_ready.clear()  # never set → will time out
        op = MountOperator(client=mock_client, config=config)
        with pytest.raises(MountTimeoutError):
            op.connect()

    def test_connect_timeout_on_mount_ready(self, config, mock_client):
        """connect() raises MountTimeoutError if mount_ready times out."""
        import importlib
        import MountOperator as mo_module
        importlib.reload(mo_module)
        from MountOperator import MountOperator
        from exceptions import MountTimeoutError

        mock_client.connection_ready.set()
        mock_client.mount_ready.clear()  # never set → will time out
        op = MountOperator(client=mock_client, config=config)
        with pytest.raises(MountTimeoutError):
            op.connect()


class TestMoveDir:
    def test_move_sends_switches(self, operator, mock_client):
        """move_dir should send a switch ON and then OFF."""
        from cardinalDirection import CardinalDirection
        operator.move_dir(direction=CardinalDirection.North, timeout=0)
        # sendNewSwitch should be called at least twice: once to start, once to stop
        assert mock_client.sendNewSwitch.call_count >= 2

    def test_move_respects_timeout(self, operator):
        """move_dir should complete approximately after timeout seconds."""
        from cardinalDirection import CardinalDirection
        start = time.monotonic()
        operator.move_dir(direction=CardinalDirection.East, timeout=0)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # should be near-instant for timeout=0

    def test_move_abortable(self, operator, mock_client):
        """move_dir should return early when abort is triggered from another thread."""
        from cardinalDirection import CardinalDirection

        def abort_after_delay():
            time.sleep(0.1)
            operator.move_abort_on()

        t = threading.Thread(target=abort_after_delay, daemon=True)
        t.start()

        start = time.monotonic()
        operator.move_dir(direction=CardinalDirection.North, timeout=10)
        elapsed = time.monotonic() - start

        t.join(timeout=2)
        assert elapsed < 2.0, "move_dir should have been aborted early"


class TestAbort:
    def test_abort_on_sends_switch(self, operator, mock_client):
        """move_abort_on should call sendNewSwitch."""
        operator.move_abort_on()
        mock_client.sendNewSwitch.assert_called()

    def test_abort_off_sends_switch(self, operator, mock_client):
        """move_abort_off should call sendNewSwitch."""
        operator.move_abort_off()
        mock_client.sendNewSwitch.assert_called()

    def test_emergency_abort_sends_both_switches(self, operator, mock_client):
        """move_emergency_abort should stop both NS and WE motion."""
        operator.move_emergency_abort()
        # Should have sent switches for both TELESCOPE_MOTION_NS and TELESCOPE_MOTION_WE
        assert mock_client.sendNewSwitch.call_count >= 2


class TestGoHome:
    def test_go_home_sends_switch(self, operator, mock_client):
        """go_home should call sendNewSwitch."""
        operator.go_home()
        mock_client.sendNewSwitch.assert_called_once()


# --- properties with named elements, so tests can check *which* switch/number was set ---

def make_vector(names, values=None):
    """A fake INDI vector property whose elements have names (and values)."""
    import PyIndi
    elements = []
    for i, n in enumerate(names):
        e = MagicMock()
        e.getName.return_value = n
        if values is not None:
            e.getValue.return_value = values[i]
        elements.append(e)
    prop = MagicMock()
    prop.__iter__ = lambda self: iter(elements)
    prop.getState.return_value = PyIndi.IPS_OK
    return prop, {e.getName(): e for e in elements}


@pytest.fixture
def named(operator):
    """Make PyIndi.PropertySwitch/PropertyNumber pass the fake property straight through."""
    import PyIndi
    PyIndi.PropertySwitch.side_effect = lambda p: p
    PyIndi.PropertyNumber.side_effect = lambda p: p
    props = {}
    operator.device.getProperty.side_effect = lambda name: props[name]
    yield props
    PyIndi.PropertySwitch.side_effect = None
    PyIndi.PropertyNumber.side_effect = None


def is_on(element):
    import PyIndi
    return element.setState.call_args.args[0] == PyIndi.ISS_ON


class TestCoordSetMode:
    def test_picks_switch_by_name_not_position(self, operator, named):
        """INDI orders ON_COORD_SET as TRACK, SLEW, SYNC; SLEW must turn on the SLEW switch."""
        from mountaction import MountMode
        named["ON_COORD_SET"], sw = make_vector(["TRACK", "SLEW", "SYNC"])
        operator.on_coord_set_mode(MountMode.SLEW)
        assert is_on(sw["SLEW"]) and not is_on(sw["TRACK"]) and not is_on(sw["SYNC"])


class TestCoordinates:
    def test_get_eod_coord_reads_by_name(self, operator, named):
        named["EQUATORIAL_EOD_COORD"], _ = make_vector(["DEC", "RA"], [45.5, 6.25])
        c = operator.get_EOD_COORD()
        assert c.right_ascension == 6.25 and c.declination == 45.5

    def test_move_coord_sets_ra_dec_and_mode(self, operator, named, mock_client):
        from coordinate import EOD_COORD
        named["ON_COORD_SET"], sw = make_vector(["TRACK", "SLEW", "SYNC"])
        named["EQUATORIAL_EOD_COORD"], num = make_vector(["RA", "DEC"], [0, 0])
        operator.move_coord(EOD_COORD(5.5, -20.0), wait=False)
        assert is_on(sw["TRACK"])
        num["RA"].setValue.assert_called_with(5.5)
        num["DEC"].setValue.assert_called_with(-20.0)
        mock_client.sendNewNumber.assert_called_once()


class TestGuide:
    def test_pulse_sets_only_its_direction(self, operator, named, mock_client):
        from cardinalDirection import CardinalDirection
        named["TELESCOPE_TIMED_GUIDE_WE"], num = make_vector(["TIMED_GUIDE_W", "TIMED_GUIDE_E"], [0, 0])
        operator.guide(CardinalDirection.West, 300, wait=False)
        num["TIMED_GUIDE_W"].setValue.assert_called_with(300)
        num["TIMED_GUIDE_E"].setValue.assert_called_with(0)
        mock_client.sendNewNumber.assert_called_once()

    def test_zero_pulse_sends_nothing(self, operator, mock_client):
        from cardinalDirection import CardinalDirection
        operator.guide(CardinalDirection.North, 0)
        mock_client.sendNewNumber.assert_not_called()


class TestSlewSpeed:
    def test_speed_is_position_one_based(self, operator, named):
        named["TELESCOPE_SLEW_RATE"], sw = make_vector(["1x", "2x", "3x", "4x"])
        operator.set_slew_speed(1)
        assert is_on(sw["1x"]) and not is_on(sw["3x"])

    def test_out_of_range_raises(self, operator, named):
        named["TELESCOPE_SLEW_RATE"], _ = make_vector(["1x", "2x"])
        with pytest.raises(ValueError):
            operator.set_slew_speed(3)


class TestWaitDone:
    def test_alert_raises(self, operator, named):
        import PyIndi
        from exceptions import MountError
        named["TELESCOPE_PARK"], _ = make_vector(["PARK", "UNPARK"])
        named["TELESCOPE_PARK"].getState.return_value = PyIndi.IPS_ALERT
        with pytest.raises(MountError):
            operator._wait_done("TELESCOPE_PARK", timeout=1)

    def test_busy_times_out(self, operator, named):
        import PyIndi
        from exceptions import MountTimeoutError
        named["TELESCOPE_PARK"], _ = make_vector(["PARK", "UNPARK"])
        named["TELESCOPE_PARK"].getState.return_value = PyIndi.IPS_BUSY
        with pytest.raises(MountTimeoutError):
            operator._wait_done("TELESCOPE_PARK", timeout=0.5)
