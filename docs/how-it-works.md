# How it works

Three things have to go right to read a KW330: it has to **power on**, **enumerate** as a serial port, and you have to understand the **stream it emits**. Each has a non-obvious gotcha.

## Power

The KW330 has a USB-C *receptacle* but is wired internally like a legacy USB-B/micro-USB device: **it omits the mandatory 5.1 kΩ CC pull-down ("Rd") resistors.** That single cost-cut explains every connection symptom.

USB-C power is gated by the **CC (Configuration Channel)** pins:

- A **source/host** advertises availability with a pull-**up** (Rp) on CC and **keeps VBUS at 0 V until it detects a sink** — i.e. until it sees the sink pulling CC down through a 5.1 kΩ **Rd**. This is a safety requirement of the USB Type-C spec, not a quirk.
- A compliant **sink/device** presents that Rd. The KW330 does not.

So:

- **C-to-C cable into a compliant USB-C host** (a Mac, a laptop, a phone): the host never sees an Rd, concludes nothing is attached, and **leaves VBUS off**. The device is completely dead — no power, no enumeration, nothing in the kernel log. It looks broken; it isn't.
- **USB-A → C cable from a USB-A port or charger**: USB-A has **no CC pin and permanently-live VBUS** (legacy behavior). A compliant A-to-C cable puts a **56 kΩ Rp in its USB-C plug** (advertising "USB Default" current) so the device sees a valid legacy source. It powers up regardless of having no Rd.
- **Powered or bus-powered USB hub**: the hub's downstream port sources VBUS the way a charger does, so the device powers up — and the hub bridges data upstream to your computer. **This is the reliable fix**, and it solves both power and data in one move.

> Aside: avoid cheap passive **USB-C-receptacle-to-USB-A-plug** adapters — that specific topology is prohibited by the spec (it lets you build illegal A-to-A cables). The inverse (A-receptacle-to-C-plug, i.e. "plug a legacy A cable into a C device") is legal *if* it carries the 56 kΩ Rp, but quality is a coin toss. A powered hub sidesteps the whole question.

**Confirming a power-only-cable diagnosis (macOS):** with the device "connected" but the bus empty, check the kernel log —

```bash
log show --last 2m --predicate 'subsystem == "com.apple.iokit.IOUSBHostFamily"' --style compact | grep -i -E 'connect|enumerat|port'
```

No events at all = the host never detected anything electrically = power/cable problem, not software.

## Enumeration (why there's no driver to install)

The KW330's MCU presents the **USB CDC-ACM** class (Communications Device Class, Abstract Control Model) with USB ID `0483:5740` — the generic "STM32 Virtual COM Port" identity. (Artery AT32 clones reuse the same ID; the silicon may be ST or ST-compatible.)

CDC-ACM is a standardized class, so every modern OS binds it automatically:

- **macOS** (since 10.14): `com.apple.driver.usb.cdc.acm` → `/dev/cu.usbmodem<serial>`
- **Linux**: in-tree `cdc_acm` module → `/dev/ttyACM0`
- **Windows 10/11**: inbox `usbser.sys`, matched on the **class/subclass (0x02/0x02)** in the device descriptor — not the VID/PID — so it binds with no INF. (Windows 7/8.1 predate inbox CDC and need the vendor `stmcdc.inf`.)

A CDC port also ignores the serial baud rate at the protocol level — the "115200" you set is nominal. (A CH340-based unit is the opposite: a real UART bridge where baud must match the firmware.)

## The "Print Data Stream" protocol

On the device, **NORMAL mode → Print Data → Print Data Stream** makes the firmware print its datastream out the serial port. Key properties, established by capture:

- **Encoding:** latin-1, not pure 7-bit ASCII — the degree symbol is a raw `0xB0` byte. Decode as latin-1 or you'll choke on it.
- **Framing:** a small binary/`$$`/STX banner at stream start, then lines terminated by **CRLF (`\r\n`)**. Each data line is `Label` + **two-or-more spaces** + `value` (e.g. `Engine RPM␣␣…␣␣674/min`). Parse with `^(.*?\S)\s{2,}(.+)$`.
- **Paged scroll, not synchronized snapshots.** This is the big one. The device streams whatever PID *page* is currently on its screen, refreshing it in place, then moves on. So:
  - Different parameters are sampled at **different instants** (~10 s apart).
  - A single "frame" rarely contains all PIDs — expect gaps/nulls.
  - Don't assume two values from different lines were measured at the same moment.
- **Time reference:** the only clock in the stream is the vehicle-reported **`Time Since Engine Start`** (seconds). `structure.py` keys the time series on it and interpolates frames that lack it (flagged `t_sec_estimated`).
- **Continuous + idempotent-once:** it loops until you stop it. Trigger it **once** — multiple triggers overlap and corrupt the stream.
- **Unsupported channels read garbage.** Some PIDs the generic tool polls don't exist on a given engine and read ceiling values (e.g. a fuel trim pinned at 99.2%, an O2 voltage stuck at 1.275 V). Treat lone outliers skeptically; cross-check against the genuine bank-1 PIDs.

## `uplink.exe`, briefly

The vendor updater is an **Inno Setup 6.1.0** installer (Delphi `MZP` stub — verified via `file`, the `MZP` magic, and embedded `Inno Setup Setup Data (6.1.0)` / `Embarcadero Delphi for Win32` strings). Unpacking it (e.g. with `innoextract`) reveals the real updater plus bundled **CH340 and STM CDC drivers** and an OBD DTC database. It talks to the device over the same serial port using a Win32 `SetCommState` protocol and fetches firmware from the vendor's server over plain HTTP. None of it is needed to read the datastream — it's only relevant if you want to flash firmware (Windows, or a Windows VM with USB passthrough).
