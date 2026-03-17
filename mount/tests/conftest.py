"""Shared fixtures and PyIndi mocks for all tests."""

import sys
import threading
from unittest.mock import MagicMock, patch
import pytest


# PyIndi is a C extension that requires a running INDI server.
# We stub it out so tests can run without hardware.
mock_pyindi = MagicMock()
mock_pyindi.IPS_IDLE = 0
mock_pyindi.IPS_OK = 1
mock_pyindi.IPS_BUSY = 2
mock_pyindi.IPS_ALERT = 3
mock_pyindi.ISS_OFF = 0
mock_pyindi.ISS_ON = 1

mock_base_client = MagicMock()
mock_pyindi.BaseClient = mock_base_client

sys.modules["PyIndi"] = mock_pyindi


@pytest.fixture
def config():
    from mountConfiguration import MountConfiguration
    return MountConfiguration(
        INDI_HOST="localhost",
        INDI_PORT=7624,
        DEVICE_NAME="iOptronV3",
        BAUD_RATE="115200",
        TIMEOUT=5,
    )


@pytest.fixture
def mock_client(config):
    """A MountControlClient with all network calls mocked out."""
    client = MagicMock()
    client.config = config
    client.connection_ready = threading.Event()
    client.mount_ready = threading.Event()
    client.connection_ready.set()
    client.mount_ready.set()
    return client


@pytest.fixture
def mock_device():
    """A mock PyIndi device."""
    device = MagicMock()

    def make_switch_prop(*switches):
        sp = MagicMock()
        sw_list = [MagicMock(name=n) for n in switches]
        for sw, n in zip(sw_list, switches):
            sw.getName.return_value = n
        sp.__iter__ = lambda self: iter(sw_list)
        return sp

    device.getProperty.side_effect = lambda name: make_switch_prop(name + "_SW")
    return device


@pytest.fixture
def operator(config, mock_client, mock_device):
    """A connected MountOperator with mocked client and device."""
    import importlib
    import MountOperator as mo_module
    importlib.reload(mo_module)
    from MountOperator import MountOperator

    op = MountOperator(client=mock_client, config=config)
    op.device = mock_device
    return op
