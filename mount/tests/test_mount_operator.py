"""Tests for MountOperator with mocked INDI client and device."""

import threading
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
