import time
import PyIndi
from datetime import datetime
from loguru import logger
from mountControlClient import MountControlClient
from mountConfiguration import MountConfiguration


def main():
    logger.info("hello iOptron!")
    logger.info("now attempting to connect to indiserver")

    client = MountControlClient()
    config = MountConfiguration()
    device = None

    client.connectServer()

    client.wait_for_device()
    device = client.getDevice(config.DEVICE_NAME)

    # now, connect to the device by toggling the CONNECTION switch to ON
    conn_prop = device.getProperty("CONNECTION")
    conn_sp = PyIndi.PropertySwitch(conn_prop)
    for sw in conn_sp:
        if sw.getName() == "CONNECT":
            sw.setState(PyIndi.ISS_ON)
        else:
            sw.setState(PyIndi.ISS_OFF)
    client.sendNewSwitch(conn_sp)
    logger.info("Connection request sent, now waiting for driver handshake......")
    time.sleep(
        3
    )  # this is unsafe. There is probably a way to access INDI and let it tell us how long to wait instead. This works for now

    """Print a human-readable status summary."""
    prop = device.getProperty("EQUATORIAL_EOD_COORD")
    np = PyIndi.PropertyNumber(prop)
    ra = dec = 0.0
    for widget in np:
        print(f"we got a widget who's name was: {widget.getName()}")
        if widget.getName() == "RA":
            print("Found RA, getting value")
            ra = widget.getValue()
            print(f"value was {widget.getValue()}")
        elif widget.getName() == "DEC":
            print("Found DEC, getting value")
            dec = widget.getValue()
            print(f"value was {dec}")

    # RA in HH:MM:SS
    ra_h = int(ra)
    ra_m = int((ra - ra_h) * 60)
    ra_s = ((ra - ra_h) * 60 - ra_m) * 60

    # DEC in DD:MM:SS
    dec_sign = "+" if dec >= 0 else "-"
    dec_abs = abs(dec)
    dec_d = int(dec_abs)
    dec_m = int((dec_abs - dec_d) * 60)
    dec_s = ((dec_abs - dec_d) * 60 - dec_m) * 60

    ra_str = f"{ra_h:02d}h {ra_m:02d}m {ra_s:05.2f}s"
    dec_str = f"{dec_sign}{dec_d:02d}° {dec_m:02d}' {dec_s:05.2f}\""

    print(f"\n{'=' * 50}")
    print(f"  iOptron CEM70 Status  —  {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'=' * 50}")
    print(f"  RA:   {ra_str}  ({ra:.6f} h)")
    print(f"  DEC:  {dec_str}  ({dec:.6f}°)")

    # The above code does not seem to work for some reason. Perhaps unparking the mount first, then gatheting position data will solve this, however I am unsure

    # unpark the mount
    logger.info("Unparking mount now")
    prop = device.getProperty("TELESCOPE_PARK")

    # now try to move north ten secs
    prop_name = "TELESCOPE_MOTION_NS"
    on_name = "MOTION_NORTH"
    prop = device.getProperty(prop_name)
    sp = PyIndi.PropertySwitch(prop)
    for sw in sp:
        if sw.getName() == on_name:
            sw.setState(PyIndi.ISS_ON)
        else:
            sw.setState(PyIndi.ISS_OFF)
    client.sendNewSwitch(sp)
    logger.info("Moving north ten secs")

    time.sleep(10)
    for sw in sp:
        if sw.getName() == on_name:
            sw.setState(PyIndi.ISS_OFF)
        else:
            sw.setState(PyIndi.ISS_OFF)
    client.sendNewSwitch(sp)


if __name__ == "__main__":
    logger.info("package currently being run in Demo mode")
    main()
