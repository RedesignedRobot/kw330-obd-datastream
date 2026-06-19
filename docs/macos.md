# macOS

Verified end to end on Apple Silicon, macOS 14/15. No driver install needed.

## 1. Connect
Plug the scanner into a powered USB hub (not directly into a USB-C/Thunderbolt port; see why in [how-it-works.md](how-it-works.md#power)), using a data cable. It should power on.

## 2. Find the port
```bash
python3 scripts/find_port.py
# or, no Python:
ls /dev/cu.usbmodem*
```
The KW330 appears as `/dev/cu.usbmodem<serial>` (CDC-ACM, handled by Apple's built-in `com.apple.driver.usb.cdc.acm`). Confirm it:
```bash
ioreg -p IOUSB -l -w 0 | grep -iE '"USB Product Name"|idVendor|idProduct'
# expect "STM32 Virtual COM Port", idVendor 1155 (0x0483), idProduct 22336 (0x5740)
```
Use `/dev/cu.*` (call-out), not `/dev/tty.*` (the tty device blocks on carrier-detect).

## 3. Capture
On the scanner: NORMAL mode, Print Data, Print Data Stream (click once).

With pyserial:
```bash
pip install pyserial
python3 scripts/capture.py            # auto-detect, Ctrl-C to stop
```

No dependencies (stty + cat):
```bash
PORT=$(ls /dev/cu.usbmodem* | head -1)
stty -f "$PORT" 115200 raw -echo
cat "$PORT" | tee capture.bin | hexdump -C
```

## 4. Structure
```bash
python3 scripts/structure.py capture.bin
```

## CH340-based units
If your scanner uses a WCH CH340 bridge instead of STM CDC, it shows up as `/dev/cu.usbserial*` or `/dev/cu.wchusbserial*`. macOS has had a native CH34x driver since 10.14 (a DriverKit dext on current releases). Do not install the legacy WCH kext; running it alongside Apple's driver creates conflicting, non-functional ports.

## Troubleshooting
- No `/dev/cu.usbmodem*` but the scanner is lit: data-cable or hub-port problem. Swap to a known data cable, try another hub port.
- Scanner fully dead: almost certainly a C-to-C cable into a USB-C port. Use a powered hub. Confirm with `log show --last 2m --predicate 'subsystem == "com.apple.iokit.IOUSBHostFamily"' --style compact`; no events means nothing was detected.
- Port opens but no bytes: you have not triggered Print Data Stream, or it is in update mode (silent until a host handshakes).
