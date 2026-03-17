import PyIndi


class Helpers:
    """Helper functions for bridging between indiserver and our client."""

    @staticmethod
    def state_str(s) -> str:
        """Converts an IPState enum into a human-readable string."""
        return {
            PyIndi.IPS_IDLE: "Idle",
            PyIndi.IPS_OK: "OK",
            PyIndi.IPS_BUSY: "Busy",
            PyIndi.IPS_ALERT: "Alert",
        }.get(s, f"Unknown({s})")

    @staticmethod
    def switch_str(s) -> str:
        """Converts an ISState enum to a human-readable string."""
        return "ON" if s == PyIndi.ISS_ON else "OFF"
