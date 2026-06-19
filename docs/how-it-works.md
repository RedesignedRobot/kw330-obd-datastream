# How it works

Three things have to go right: the device must power on, enumerate as a serial port, and you have to understand the stream it emits. Each has a non-obvious catch.

## Power

The KW330 has a USB-C receptacle but is wired internally like a legacy USB-B/micro-USB device: it omits the mandatory 5.1k CC pull-down ("Rd") resistors. That one cost-cut explains every connection symptom.

USB-C power is gated by the CC (Configuration Channel) pins:

- A source/host advertises itself with a pull-up (Rp) on CC and keeps VBUS at 0 V until it detects a sink, meaning it sees the sink pulling CC down through a 5.1k Rd. This is a safety requirement of the USB Type-C spec, not a quirk.
- A compliant sink presents that Rd. The KW330 does not.

So:

- C-to-C cable into a compliant USB-C host (Mac, laptop, phone): the host never sees an Rd, decides nothing is attached, and leaves VBUS off. The device is fully dead, with no entry in the kernel log. It looks broken but is not.
- USB-A to C cable from a USB-A port or charger: USB-A has no CC pin and permanently live VBUS (legacy behavior). A compliant A-to-C cable puts a 56k Rp in its USB-C plug, so the device sees a valid legacy source and powers up despite having no Rd.
- Powered or bus-powered USB hub: the hub's downstream port sources VBUS like a charger, so the device powers up, and the hub bridges data to your computer. This is the reliable fix, solving power and data at once.

Avoid cheap passive USB-C-receptacle-to-USB-A-plug adapters; that exact topology is prohibited by the spec, because it allows illegal A-to-A cables. The inverse (A-receptacle-to-C-plug) is legal if it carries the 56k Rp, but quality varies. A powered hub sidesteps the question.

To confirm a power-only-cable diagnosis on macOS, with the device "connected" but the bus empty:

```bash
log show --last 2m --predicate 'subsystem == "com.apple.iokit.IOUSBHostFamily"' --style compact | grep -i -E 'connect|enumerat|port'
```

No events at all means the host never detected anything electrically, so it is a power or cable problem, not software.

## Enumeration (why there is no driver to install)

The KW330's MCU presents the USB CDC-ACM class with USB ID `0483:5740`, the generic "STM32 Virtual COM Port" identity. (Artery AT32 clones reuse the same ID, so the silicon may be ST or ST-compatible.)

CDC-ACM is a standard class, so every modern OS binds it automatically:

- macOS (since 10.14): `com.apple.driver.usb.cdc.acm`, giving `/dev/cu.usbmodem<serial>`
- Linux: in-tree `cdc_acm`, giving `/dev/ttyACM0`
- Windows 10/11: inbox `usbser.sys`, matched on the class/subclass (0x02/0x02) in the descriptor rather than the VID/PID, so it binds with no INF. (Windows 7/8.1 predate inbox CDC and need the vendor `stmcdc.inf`.)

A CDC port ignores the serial baud rate at the protocol level, so the "115200" you set is nominal. A CH340-based unit is the opposite: a real UART bridge where baud must match the firmware.

## The "Print Data Stream" protocol

On the device, NORMAL mode then Print Data then Print Data Stream makes the firmware print its datastream out the serial port. Properties established by capture:

- Encoding: latin-1, not pure 7-bit ASCII. The degree symbol is a raw `0xB0` byte, so decode as latin-1.
- Framing: a small binary banner at the start, then CRLF (`\r\n`) lines. Each data line is `Label`, two or more spaces, then `value` (for example `Engine RPM` then padding then `674/min`). Parse with `^(.*?\S)\s{2,}(.+)$`.
- Paged scroll, not synchronized snapshots. The device streams whatever PID page is on its screen, refreshing it in place, then moves on. So different parameters are sampled at different instants (about 10 s apart), a single frame rarely holds all PIDs (expect gaps), and you should not assume two values from different lines were read at the same moment.
- Time reference: the only clock is the vehicle's "Time Since Engine Start" (seconds). `structure.py` keys the series on it and interpolates frames that lack it (flagged `t_sec_estimated`).
- Continuous, trigger once: it loops until stopped. Trigger it once; repeated triggers overlap and corrupt the stream.
- Unsupported channels read garbage. Some PIDs the generic tool polls do not exist on a given engine and read ceiling values (a fuel trim pinned at 99.2%, an O2 voltage stuck at 1.275 V). Treat lone outliers with suspicion and cross-check the genuine bank-1 PIDs.

## uplink.exe, briefly

The vendor updater is an Inno Setup 6.1.0 installer (Delphi `MZP` stub, confirmed via `file`, the `MZP` magic, and embedded `Inno Setup Setup Data (6.1.0)` and `Embarcadero Delphi for Win32` strings). Unpacking it (for example with `innoextract`) reveals the real updater plus bundled CH340 and STM CDC drivers and an OBD code database. It talks to the device over the same serial port with a Win32 `SetCommState` protocol and fetches firmware over plain HTTP. None of it is needed to read the datastream; it only matters if you want to flash firmware (Windows, or a Windows VM with USB passthrough).
