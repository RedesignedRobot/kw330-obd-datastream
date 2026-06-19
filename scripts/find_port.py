#!/usr/bin/env python3
"""
find_port.py: list serial ports and flag the likely KW330.

    pip install pyserial
    python3 find_port.py

Useful when auto-detection fails or you want to confirm the device enumerated.
On macOS the KW330 shows as /dev/cu.usbmodem*, on Linux /dev/ttyACM0 (CDC) or
/dev/ttyUSB0 (CH340), on Windows COMx.
"""
import sys

KNOWN_IDS = {
    (0x0483, 0x5740),
    (0x1A86, 0x7523), (0x1A86, 0x7522), (0x1A86, 0x5523), (0x1A86, 0xE523),
    (0x4348, 0x5523),
}


def main():
    try:
        from serial.tools import list_ports
    except ImportError:
        sys.exit("pyserial is required:  pip install pyserial")

    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found. Is the device plugged in (via a powered hub) and powered on?")
        return
    print(f"{'DEVICE':<28} {'VID:PID':<10} DESCRIPTION")
    print("-" * 70)
    for p in sorted(ports, key=lambda x: x.device):
        vidpid = f"{p.vid:04x}:{p.pid:04x}" if p.vid is not None else "--:--"
        flag = "  <-- likely KW330" if p.vid is not None and (p.vid, p.pid) in KNOWN_IDS else ""
        print(f"{p.device:<28} {vidpid:<10} {p.description}{flag}")


if __name__ == "__main__":
    main()
