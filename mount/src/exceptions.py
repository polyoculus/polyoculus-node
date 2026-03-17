class MountError(Exception):
    """Base exception for all mount errors."""
    pass


class MountConnectionError(MountError):
    """Raised when connecting to the mount or INDI server fails."""
    pass


class MountTimeoutError(MountConnectionError):
    """Raised when waiting for a device or property times out."""
    pass
