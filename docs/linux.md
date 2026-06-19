# Linux

No driver to install: `cdc_acm` (STM) and `ch341` (CH340) are in-tree on every modern distro kernel and auto-load on plug-in. The one real catch is ModemManager.

## 1. Connect
Plug the scanner into a powered USB hub with a data cable (see [how-it-works.md](how-it-works.md#power)). It should power on.

## 2. Find the port
```bash
lsusb | grep -iE '0483:5740|1a86'        # confirm it enumerated
ls -l /dev/serial/by-id/                 # stable names (preferred)
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
dmesg | grep -iE 'cdc_acm|ch341|ttyACM|ttyUSB' | tail
```
STM CDC (`0483:5740`) gives `/dev/ttyACM0`, bound by `cdc_acm`. Prefer the stable symlink `/dev/serial/by-id/usb-STMicroelectronics_*-if00`, since ttyACM numbering depends on plug order. CH340 (`1A86:*`) gives `/dev/ttyUSB0`, bound by `ch341`.

## 3. Tame ModemManager (do this first)
On most desktop distros, ModemManager probes new `ttyACM` ports with AT commands on plug-in. It grabs the port and injects bytes, corrupting the first seconds of capture or causing "Device or resource busy". Tell it to ignore the device:

```bash
sudo tee /etc/udev/rules.d/99-kw330-mm-ignore.rules >/dev/null <<'EOF'
# KW330 STM32 Virtual COM Port
ACTION=="add|change", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", ENV{ID_MM_DEVICE_IGNORE}="1"
# CH340-based units
ACTION=="add|change", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTRS{idVendor}=="1a86", ENV{ID_MM_DEVICE_IGNORE}="1"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
# replug, then verify the flag landed:
udevadm info -q property -n /dev/ttyACM0 | grep ID_MM_DEVICE_IGNORE   # shows =1
```
If you have no cellular modem at all, the blunt alternative is `sudo systemctl mask ModemManager`.

## 4. Permissions
Serial nodes are group-owned. Add yourself to the right group; the name differs by distro, so check first:
```bash
ls -l /dev/ttyACM0                                        # read the group column
sudo usermod -aG "$(stat -c '%G' /dev/ttyACM0)" "$USER"   # dialout on Debian/Ubuntu/Fedora, uucp on Arch
```
Then log out and back in (or run `newgrp dialout`). Do not `chmod 666` the node; it does not survive replug.

## 5. Capture
On the scanner: NORMAL mode, Print Data, Print Data Stream (click once).

With pyserial:
```bash
pip install pyserial        # or: sudo apt install python3-serial
python3 scripts/capture.py  # auto-detect, Ctrl-C to stop
```

No dependencies (stty + cat):
```bash
PORT=/dev/serial/by-id/usb-STMicroelectronics_*-if00   # or /dev/ttyACM0
stty -F $PORT 115200 raw -echo
cat $PORT > capture.bin             # raw, binary-safe
# live hex view:  cat $PORT | tee capture.bin | xxd
```
Check nothing else holds the port: `sudo lsof /dev/ttyACM0`.

## 6. Structure
```bash
python3 scripts/structure.py capture.bin
```
