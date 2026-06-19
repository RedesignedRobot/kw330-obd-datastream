#!/usr/bin/env python3
"""
capture.py — read the KW330 (and CDC/CH340-based KONNWEI tools) serial stream.

Cross-platform (macOS / Linux / Windows). Auto-detects the device by USB VID/PID,
opens the port, and writes every received byte to a .bin while echoing a live
hex+ASCII view. Stop with Ctrl-C.

    pip install pyserial
    python3 capture.py                 # auto-detect, capture until Ctrl-C
    python3 capture.py --seconds 120   # capture for a fixed window
    python3 capture.py --port /dev/ttyACM0 --baud 115200

The device must be in NORMAL mode, and you must trigger "Print Data -> Print Data
Stream" on the unit for data to flow. See the repo README.
"""
import argparse, sys, time

# USB IDs seen across the KW family: STM/Artery CDC-ACM, and WCH CH340/CH341.
KNOWN_IDS = {
    (0x0483, 0x5740),  # STMicroelectronics "STM32 Virtual COM Port" (also Artery AT32)
    (0x1A86, 0x7523), (0x1A86, 0x7522), (0x1A86, 0x5523), (0x1A86, 0xE523),
    (0x4348, 0x5523),  # WCH CH340/CH341 (and an older clone)
}
DESC_HINTS = ("virtual com", "cdc", "ch340", "ch341", "usb serial", "usbmodem")


def find_port():
    from serial.tools import list_ports
    fallback = []
    for p in list_ports.comports():
        if p.vid is not None and (p.vid, p.pid) in KNOWN_IDS:
            return p.device, f"{p.vid:04x}:{p.pid:04x} {p.description}"
        hay = f"{p.description} {p.device}".lower()
        if any(h in hay for h in DESC_HINTS):
            fallback.append((p.device, p.description))
    return (fallback[0][0], fallback[0][1]) if fallback else (None, None)


def hexdump_line(offset, chunk):
    hexs = " ".join(f"{b:02x}" for b in chunk).ljust(48)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    return f"{offset:08x}  {hexs}  |{asc}|"


def main():
    ap = argparse.ArgumentParser(description="Capture a KW330 serial datastream.")
    ap.add_argument("--port", help="serial device (auto-detected if omitted)")
    ap.add_argument("--baud", type=int, default=115200, help="nominal baud (CDC ignores it; default 115200)")
    ap.add_argument("--seconds", type=float, default=0, help="capture window in seconds (0 = until Ctrl-C)")
    ap.add_argument("--out", help="output .bin path (default kw330_capture_<timestamp>.bin)")
    ap.add_argument("--quiet", action="store_true", help="don't echo the live hex view")
    args = ap.parse_args()

    try:
        import serial  # noqa: F401
    except ImportError:
        sys.exit("pyserial is required:  pip install pyserial")
    import serial

    port, info = (args.port, "(explicit)") if args.port else find_port()
    if not port:
        sys.exit("No KW330-like serial port found. Plug the device in (NORMAL mode, via a "
                 "powered hub), then run:  python3 find_port.py")
    out = args.out or f"kw330_capture_{time.strftime('%Y%m%d_%H%M%S')}.bin"

    print(f">>> port   : {port}  {info}")
    print(f">>> baud   : {args.baud} (nominal)")
    print(f">>> output : {out}")
    print(f">>> window : {'until Ctrl-C' if args.seconds == 0 else str(args.seconds) + 's'}")
    print(">>> Trigger 'Print Data -> Print Data Stream' on the device now.\n")

    total, offset = 0, 0
    deadline = time.time() + args.seconds if args.seconds else None
    with serial.Serial(port, args.baud, timeout=0.5) as ser, open(out, "wb") as f:
        # Asserting DTR/RTS makes some firmwares believe a host is present.
        ser.dtr = True
        ser.rts = True
        try:
            while deadline is None or time.time() < deadline:
                chunk = ser.read(4096)
                if not chunk:
                    continue
                f.write(chunk); f.flush()
                total += len(chunk)
                if not args.quiet:
                    for i in range(0, len(chunk), 16):
                        print(hexdump_line(offset + i, chunk[i:i + 16]))
                    offset += len(chunk)
        except KeyboardInterrupt:
            pass
    print(f"\n>>> done: {total} bytes -> {out}")
    print(f">>> structure it:  python3 structure.py {out}")


if __name__ == "__main__":
    main()
