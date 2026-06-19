# Windows

On Windows 10/11 the STM-based KW330 needs no driver; the inbox `usbser.sys` binds it automatically.

## 1. Connect
Plug the scanner into a powered USB hub with a data cable (see [how-it-works.md](how-it-works.md#power)). It should power on.

## 2. Driver
STM CDC (`0483:5740`): Windows 10/11 auto-loads inbox `usbser.sys` (it matches the CDC class 02/02 in the descriptor, not the VID/PID), so it appears as `STMicroelectronics Virtual COM Port (COMx)` with nothing to install. (Windows 7/8.1 only: install the vendor `stmcdc.inf` / ST VCP package.)

CH340-based units (`1A86:7523`): Windows Update usually fetches the signed WCH driver. If you get a yellow-bang "unknown device", install `CH341SER.EXE` from WCH only (`wch-ic.com` / `wch.cn`) or a trusted board vendor, as Administrator. Avoid "driver updater" sites.

## 3. Find the COM port
```powershell
# fastest:
[System.IO.Ports.SerialPort]::GetPortNames()

# with names and hardware IDs:
Get-PnpDevice -Class Ports -Status OK | Select-Object FriendlyName, InstanceId
#   STM:   ...VID_0483&PID_5740...   "STMicroelectronics Virtual COM Port (COM5)"
#   CH340: ...VID_1A86&PID_7523...   "USB-SERIAL CH340 (COM5)"
```
Or use Device Manager, Ports (COM & LPT); unplug/replug to see which entry appears.

## 4. Capture
On the scanner: NORMAL mode, Print Data, Print Data Stream (click once). Set 8 data bits, no parity, 1 stop bit, flow control None (leaving RTS/CTS or XON/XOFF on can stall a device with no handshake lines).

Python pyserial (recommended, cross-platform):
```powershell
pip install pyserial
python scripts\capture.py --port COM5        # or omit --port to auto-detect
python scripts\structure.py kw330_capture_*.bin
```

GUI terminals:
- RealTerm, best for raw/binary: Port tab, set COM and baud, 8N1, flow None, Open; Capture tab, set filename, Direct Capture, Start. True raw bytes plus hex view.
- PuTTY, quick live view: connection type Serial, set COM and speed, 8N1, flow None; Session, Logging, All session output, file path. PuTTY logs printable and control bytes, not a clean hex dump.
- Termite, minimal, good for line-based ASCII with "Log to file".

## 5. Structure
```powershell
python scripts\structure.py capture.bin
```

## Troubleshooting
- "Access is denied" or port busy: only one app can hold a COM port; close the other one.
- Garbage characters: wrong baud (matters for CH340; pure CDC ignores baud). Set 8N1.
- Nothing arrives: flow control is not None, or you have not triggered Print Data Stream.
- COM 10 or higher: some old tools need the `\\.\COM10` form; PuTTY and pyserial accept the plain name.
