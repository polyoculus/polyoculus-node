from dataclasses import dataclass
import PyIndi


@dataclass
class Helpers:
    """
    Some helper functions to assist with bridging between Indiserver and our client
    """

    def state_str(s):
        """Converts an IPState enum into a human-readable string

        Returns: a human readable string, depending on the IPState

        """
        return {
            PyIndi.IPS_IDLE: "Idle",
            PyIndi.IPS_OK: "OK",
            PyIndi.IPS_BUSY: "Busy",
            PyIndi.IPS_ALERT: "Alert",
        }.get(s, f"Unknown({s})")

    def switch_str(s):
        """Converts a ISState enum to a human-readable string.

        Returns: a human-readable string, depending on the ISState

        """
        return "ON" if s == PyIndi.ISS_ON else "OFF"
