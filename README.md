# KW330 OBD Data Access

**Read the live OBD-II datastream from a KONNWEI KW330 (and most of the KONNWEI handheld family) on macOS, Linux, or Windows — no Windows-only vendor software, no third-party drivers.**

The KW330 is a cheap handheld OBD-II scanner. Its USB port is officially "for firmware updates only," via a Windows-only updater (`uplink.exe`). But the device also exposes a plain **USB CDC serial port**, and its on-device **Print Data → Print Data Stream** function pushes the entire live datastream out of that port as readable text. That means you can log and analyze your car's data from any OS with a few lines of Python.

This repo is the result of reverse-engineering exactly how, including the two traps that make people give up: **power delivery** and a **silent serial port**.

---

## TL;DR

```bash
pip install pyserial

python3 scripts/find_port.py          # confirm the device enumerated, get its port
python3 scripts/capture.py            # auto-detects, captures until Ctrl-C
#   → on the scanner: NORMAL mode → Print Data → Print Data Stream (click ONCE)
python3 scripts/structure.py kw330_capture_*.bin   # → time-series JSON
```

You get a raw `.bin` of the stream and a structured `*.json` time series (per-PID, clocked on the vehicle's "Time Since Engine Start"). See [`samples/`](samples/) for examples.

---

## ⚡ Trap #1 — Power: "it lights up on a charger but is dead on my Mac"

This wastes everyone's first afternoon. **The KW330's USB-C port omits the mandatory CC resistors**, so it is not a spec-compliant USB-C device — it's a legacy port in a USB-C shell.

| How you connect it | Result | Why |
|---|---|---|
| Wall charger / USB-A → C cable | ✅ powers on | USB-A VBUS is always live; the A-to-C cable carries the 56 kΩ Rp the device lacks |
| **C-to-C cable into a Mac / laptop USB-C port** | ❌ **completely dead** | A compliant USB-C host keeps VBUS **off** until it sees a sink's 5.1 kΩ Rd. The device has none → host sees "nothing plugged in" |
| **Through a powered USB hub** | ✅ **works** | The hub's downstream port sources VBUS unconditionally |

**Fix: connect the scanner through a powered (or bus-powered) USB hub, not directly to a USB-C port.** Full electrical explanation in [docs/how-it-works.md](docs/how-it-works.md#power).

## 🔌 Trap #2 — Cable: "it powers up but never appears on the computer"

Powering up only proves VBUS reached it. **You also need a real *data* cable** — many USB cables are charge-only (no D+/D- lines). If the device lights up but no serial port appears, swap the cable for one you've actually transferred files with.

---

## What the computer sees

The KW330 enumerates as a standard **USB CDC-ACM serial device — `STM32 Virtual COM Port`, USB ID `0483:5740`**. Every modern OS has a built-in driver; **nothing to install.**

| OS | Device node | Driver (built-in) |
|---|---|---|
| **macOS** (10.14+) | `/dev/cu.usbmodem*` | `com.apple.driver.usb.cdc.acm` |
| **Linux** | `/dev/ttyACM0` (prefer `/dev/serial/by-id/usb-STMicroelectronics_*-if00`) | `cdc_acm` (in-tree) |
| **Windows** 10/11 | `COMx` | inbox `usbser.sys` (auto-binds the CDC class) |

> Some cheaper units in the family use a **WCH CH340** UART bridge (`1A86:7523`) instead — that shows up as `/dev/ttyUSB0` / `/dev/cu.wchusbserial*` / a CH340 COM port and may need the WCH driver on Windows/older macOS. We have **not** confirmed any CH340-based KW330 specifically; the KW330 we tested is STM CDC. See the per-OS guides.

**Per-OS step-by-step:** [macOS](docs/macos.md) · [Linux](docs/linux.md) · [Windows](docs/windows.md)

---

## Getting the data

1. **Connect** the scanner through a powered hub with a data cable (Traps #1/#2).
2. **Confirm the port:** `python3 scripts/find_port.py`
3. **Put the scanner in NORMAL mode** and navigate to **Print Data → Print Data Stream**. (Do *not* pick **Clear/Erase** — that wipes stored trouble codes.)
4. **Start the capture, then trigger the stream:**
   ```bash
   python3 scripts/capture.py --seconds 0     # 0 = until Ctrl-C
   ```
   Click **Print Data Stream once.** It streams continuously and loops; clicking it repeatedly overlaps and garbles the output.
5. **Structure it:** `python3 scripts/structure.py <capture>.bin` → JSON.

### The stream format

The device emits a continuous text feed — **latin-1** (not pure ASCII: a `0xB0` byte is the degree symbol), CRLF line endings, with a tiny binary banner at the start. Each line is `Label` + two-or-more spaces + `value`:

```
 Engine Coolant Temperature                         85 °C
 Engine RPM                                          674/min
 Vehicle Speed                                       2km/h
 Control module voltage                              13.82V
```

`structure.py` parses this into JSON. **Important:** the KW330 streams a *paged scroll* — it sends whatever PID page is on its screen, so different parameters are sampled at slightly different instants (~10 s apart), and a single sample rarely contains every PID. The only time reference is the vehicle-reported **`Time Since Engine Start`** (seconds), which the script uses as the clock. Read `capture_meta.IMPORTANT_caveats` in the output before trusting the numbers. Details: [docs/how-it-works.md](docs/how-it-works.md#the-print-data-stream-protocol).

---

## Does this work on my model?

The "Print Data" family of menu items + USB serial exists on the **handheld** KONNWEI scanners, not the Bluetooth/Wi-Fi dongles.

- **✅ Has USB serial + Print Data:** KW330, KW850, KW860, KW830, KW818, KW680, KW590, KW350, KW360, KW450, KW460, KW480, KW681, KW870, KW880, KW890, KW206
- **❌ No USB-to-PC / Print Data:** KW208, KW510, KW808, KW320, KW310, KW309
- **📱 Bluetooth/Wi-Fi ELM327 dongles (phone app only, not this method):** KW902, KW903, KW905, KW912

Menu wording varies: **Print Data, Print Data Stream, Print Freeze Data, Print DTC, Print All.** Behavior also varies — on some models the Print menu is built to push *stored* data to the vendor's `uplink` PC app, whereas on the KW330 we observed a genuinely **live, continuously-updating** feed.

---

## What about `uplink.exe`?

It's just the vendor's Windows updater — an **Inno Setup 6.1.0** installer (Delphi) that unpacks the real updater app plus CH340/STM USB-serial drivers. It is **Windows-only** and **not needed** to read data on any platform with this method. (It also phones home over plain HTTP to fetch firmware — fine, but not something you need.)

---

## Repo layout

```
scripts/
  find_port.py    list serial ports, flag the KW330
  capture.py      auto-detect + capture the raw stream (pyserial)
  structure.py    raw capture → time-series JSON (no dependencies)
docs/
  how-it-works.md USB-C power negotiation, CDC enumeration, the stream protocol
  macos.md  linux.md  windows.md
samples/
  raw_datastream_frame.txt    one frame, VIN redacted
  timeseries_example.json     structured output, VIN redacted
```

---

## ⚠️ Safety & legal

- **Read-only.** This reads the datastream the scanner already prints. It does not write to the vehicle. Never select **Clear/Erase** on the device unless you intend to wipe stored codes.
- **Don't operate a scanner while driving.** Capture as a passenger, or stationary.
- **PII:** OBD streams contain your **VIN**. The samples here are redacted — redact yours before sharing.
- No affiliation with KONNWEI. "KW330"/"KONNWEI" are used only to identify the hardware. Provided as-is under the [MIT License](LICENSE), no warranty.

---

*Reverse-engineered through a hands-on debugging session (macOS verified end-to-end; Linux/Windows specifics validated against vendor and kernel documentation). Documentation prepared with AI assistance. Corrections and other-model reports welcome — open an issue or PR.*
