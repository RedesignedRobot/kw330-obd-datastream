# KW330 OBD Data Access

Read the live OBD-II datastream from a KONNWEI KW330 (and most of the KONNWEI handheld family) on macOS, Linux, or Windows, with no Windows-only software and no third-party drivers.

The KW330 is a cheap handheld OBD-II scanner. Its USB port is officially "for firmware updates only" (via a Windows-only updater, `uplink.exe`), but the device also exposes a plain USB CDC serial port, and its on-device "Print Data > Print Data Stream" function pushes the whole live datastream out of it as readable text. So you can log and analyze your car's data from any OS with a few lines of Python.

We studied the device and built the small toolkit here. Two things trip people up first: power delivery, and a serial port that stays silent until you trigger it.

## TL;DR

```bash
pip install pyserial
python3 scripts/find_port.py            # confirm the device, get its port
python3 scripts/capture.py              # auto-detects; captures until Ctrl-C
#   on the scanner: NORMAL mode > Print Data > Print Data Stream (click once)
python3 scripts/structure.py kw330_capture_*.bin   # raw to time-series JSON
```

You get a raw `.bin` and a structured `*.json` time series (per-PID, clocked on the vehicle's "Time Since Engine Start"). Examples in `samples/`.

## Trap 1: power ("lights up on a charger, dead on my Mac")

The KW330's USB-C port omits the mandatory CC resistors, so it is not a spec-compliant USB-C device; it is a legacy port in a USB-C shell.

| Connection | Result | Why |
|---|---|---|
| Wall charger or USB-A to C cable | Powers on | USB-A VBUS is always live; the A-to-C cable carries the 56k Rp the device lacks |
| C-to-C cable into a Mac/laptop USB-C port | Dead | A compliant host keeps VBUS off until it sees a sink's 5.1k Rd, which the device has none of |
| Through a powered USB hub | Works | The hub's downstream port sources VBUS unconditionally |

Fix: connect the scanner through a powered (or bus-powered) USB hub, not directly to a USB-C port. Electrical detail in [docs/how-it-works.md](docs/how-it-works.md#power).

## Trap 2: cable ("powers up but never appears on the computer")

Powering up only proves VBUS reached it. You also need a real data cable; many cables are charge-only (no D+/D- lines). If it lights up but no serial port appears, swap to a cable you have actually moved files with.

## What the computer sees

The KW330 enumerates as a standard USB CDC-ACM serial device, `STM32 Virtual COM Port`, USB ID `0483:5740`. Every modern OS has a built-in driver; nothing to install.

| OS | Device node | Built-in driver |
|---|---|---|
| macOS (10.14+) | `/dev/cu.usbmodem*` | `com.apple.driver.usb.cdc.acm` |
| Linux | `/dev/ttyACM0` (prefer `/dev/serial/by-id/usb-STMicroelectronics_*-if00`) | `cdc_acm` |
| Windows 10/11 | `COMx` | inbox `usbser.sys` |

Some cheaper units in the family use a WCH CH340 bridge (`1A86:7523`) instead, which appears as `/dev/ttyUSB0`, `/dev/cu.wchusbserial*`, or a CH340 COM port and may need the WCH driver on Windows or older macOS. We did not confirm a CH340-based KW330; the unit we tested is STM CDC.

Per-OS steps: [macOS](docs/macos.md), [Linux](docs/linux.md), [Windows](docs/windows.md).

## Getting the data

1. Connect through a powered hub with a data cable (Traps 1 and 2).
2. Confirm the port: `python3 scripts/find_port.py`
3. On the scanner, in NORMAL mode, go to Print Data > Print Data Stream. Do not pick Clear/Erase; that wipes stored trouble codes.
4. Start the capture, then trigger the stream:
   ```bash
   python3 scripts/capture.py --seconds 0      # 0 = until Ctrl-C
   ```
   Click Print Data Stream once. It streams continuously and loops; repeated clicks overlap and garble the output.
5. Structure it: `python3 scripts/structure.py <capture>.bin`

### Stream format

A continuous text feed in latin-1 (not pure ASCII: `0xB0` is the degree symbol), CRLF line endings, with a small binary banner at the start. Each line is `Label`, two or more spaces, then `value`:

```
 Engine Coolant Temperature                         85 °C
 Engine RPM                                          674/min
 Vehicle Speed                                       2km/h
```

`structure.py` parses this. One caveat that matters: the KW330 streams a paged scroll. It sends whatever PID page is on its screen, so different parameters are sampled at slightly different instants (about 10 s apart), and a single sample rarely holds every PID. The only clock in the stream is the vehicle's "Time Since Engine Start" (seconds), which the script keys on. Read `capture_meta.IMPORTANT_caveats` in the output. More in [docs/how-it-works.md](docs/how-it-works.md#the-print-data-stream-protocol).

## Does this work on my model?

The "Print Data" menu and USB serial exist on the handheld scanners, not the Bluetooth/Wi-Fi dongles.

- Has USB serial and Print Data: KW330, KW850, KW860, KW830, KW818, KW680, KW590, KW350, KW360, KW450, KW460, KW480, KW681, KW870, KW880, KW890, KW206
- No USB-to-PC / Print Data: KW208, KW510, KW808, KW320, KW310, KW309
- Bluetooth/Wi-Fi ELM327 dongles (phone app only, not this method): KW902, KW903, KW905, KW912

Menu wording varies: Print Data, Print Data Stream, Print Freeze Data, Print DTC, Print All. On some models the Print menu pushes stored data to the vendor's `uplink` app; on the KW330 we saw a genuinely live, continuously updating feed.

## What about uplink.exe?

It is the vendor's Windows updater: an Inno Setup 6.1.0 installer (Delphi) that unpacks the real updater plus CH340/STM serial drivers. It is Windows-only and not needed to read data with this method.

## Repo layout

```
scripts/   find_port.py, capture.py, structure.py
docs/      how-it-works.md, macos.md, linux.md, windows.md
samples/   raw_datastream_frame.txt, timeseries_example.json (VIN redacted)
```

## Safety and legal

- Read-only. This reads the datastream the scanner already prints; it does not write to the vehicle. Never select Clear/Erase on the device unless you mean to wipe stored codes.
- Do not operate a scanner while driving. Capture as a passenger or while stationary.
- OBD streams contain your VIN. The samples here are redacted; redact yours before sharing.
- No affiliation with KONNWEI. Names are used only to identify the hardware. MIT licensed, no warranty.

We studied the device hands-on (macOS verified end to end; Linux and Windows specifics checked against vendor and kernel documentation) and built the tooling here. Documentation prepared with AI assistance. Corrections and other-model reports welcome.
