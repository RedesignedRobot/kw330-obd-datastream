#!/usr/bin/env python3
"""
structure.py: turn a KW330 "Print Data Stream" capture into time-series JSON.

    python3 structure.py kw330_capture_20260619.bin           # -> *.json next to it
    python3 structure.py capture.bin --out trip.json

The KW330 streams a *paged live scroll*: it sends whatever PID page is on its
screen, refreshed in place, so different parameters are sampled ~10 s apart and a
single frame rarely contains every PID. The only time reference in the stream is
the vehicle's "Time Since Engine Start" (seconds), which we use as the clock and
interpolate across frames that lack it. Read capture_meta.IMPORTANT_caveats in the
output before trusting the numbers. No external dependencies.
"""
import argparse, json, os, re, sys

NUM = re.compile(r"^(-?\d+(?:\.\d+)?)\s*(°\s?[CF]|kPa|km/h|/min|g/s|kg/h|Nm|km|KM|sec\.?|mA|%|V|°)?")
STATUS = ["ISO15765-4 CAN(11bit)", "No Supported", "English", "EOBD", "GAS", "CL", "OL", "---", "N/A"]


def key(label):
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def clean(v):
    v = v.strip()
    m = NUM.match(v)
    if m and m.group(1):
        unit = (m.group(2) or "").replace(" ", "")
        return (float(m.group(1)) if "." in m.group(1) else int(m.group(1))), unit, None
    for s in STATUS:
        if v.startswith(s):
            return None, None, s
    return None, None, re.split(r"\s{2,}", v)[0][:24]


def parse(text):
    pairs, vin, proto = [], None, None
    for line in text.split("\r\n"):
        s = line.strip()
        if not s or set(s) <= set("*") or "Datastream" in s:
            continue
        if s.startswith("VIN"):
            vin = s.split(":", 1)[1].strip(); continue
        if s.startswith("Protocol Type"):
            proto = s.split(":", 1)[1].strip() if ":" in s else None; continue
        if s.startswith("Language"):
            continue
        s = re.sub(r"^[a-z]\s(?=[A-Z])", "", s)            # strip stray framing char
        m = re.match(r"^(.*?\S)\s{2,}(.+)$", s)
        if m:
            pairs.append((m.group(1).strip(), m.group(2)))

    frames, cur, seen, params = [], {}, set(), {}
    for label, val in pairs:
        k = key(label)
        if k in seen:                                       # label repeats -> new frame
            frames.append(cur); cur, seen = {}, set()
        num, unit, status = clean(val)
        cur[k] = num if num is not None else status
        params.setdefault(k, {"name": label, "unit": unit or ""})
        if unit and not params[k]["unit"]:
            params[k]["unit"] = unit
        seen.add(k)
    if cur:
        frames.append(cur)
    return frames, params, vin, proto


def phase(f):
    rpm, spd = f.get("engine_rpm"), f.get("vehicle_speed")
    if isinstance(rpm, (int, float)) and rpm == 0:
        return "engine_off"
    if isinstance(spd, (int, float)) and spd > 0:
        return "driving"
    return "idle"


def interpolate(frames):
    anchors = [(i, f["time_since_engine_start"]) for i, f in enumerate(frames)
               if isinstance(f.get("time_since_engine_start"), (int, float))]

    def at(fi):
        if not anchors:
            return None, None
        for af, av in anchors:
            if af == fi:
                return av, False
        bef = [a for a in anchors if a[0] < fi]
        aft = [a for a in anchors if a[0] > fi]
        if bef and aft:
            (f0, t0), (f1, t1) = bef[-1], aft[0]
        elif len(bef) >= 2:
            (f0, t0), (f1, t1) = bef[-2], bef[-1]
        elif len(aft) >= 2:
            (f0, t0), (f1, t1) = aft[0], aft[1]
        else:
            return anchors[0][1], True
        slope = (t1 - t0) / (f1 - f0) if f1 != f0 else 0
        return round(t0 + slope * (fi - f0), 1), True

    return [at(i) for i in range(len(frames))], anchors


def main():
    ap = argparse.ArgumentParser(description="Structure a KW330 datastream capture into time-series JSON.")
    ap.add_argument("input", help="raw capture (.bin or .txt)")
    ap.add_argument("--out", help="output JSON (default: <input>.json)")
    args = ap.parse_args()

    text = open(args.input, "rb").read().decode("latin1")
    frames, params, vin, proto = parse(text)
    if not frames:
        sys.exit("No datastream frames parsed. Was this a 'Print Data Stream' capture?")

    times, anchors = interpolate(frames)
    samples = []
    for i, f in enumerate(frames):
        t, est = times[i]
        rec = {"frame": i, "t_sec": t, "t_sec_estimated": est, "phase": phase(f)}
        rec.update(f)
        samples.append(rec)
    samples.sort(key=lambda r: (r["t_sec"] is None, r["t_sec"]))

    ts = [a[1] for a in anchors]
    doc = {
        "capture_meta": {
            "source": "KONNWEI KW330 - Print Data Stream over USB CDC",
            "vehicle_vin": vin,
            "protocol": proto,
            "time_basis": "t_sec = vehicle 'Time Since Engine Start' (sec). t_sec_estimated=true means interpolated by frame index.",
            "engine_run_span_sec": ({"start": min(ts), "end": max(ts), "duration_sec": max(ts) - min(ts)} if ts else None),
            "sample_count": len(samples),
            "IMPORTANT_caveats": [
                "PAGED SCROLL, not synchronized snapshots: different PIDs were sampled at different instants (~10s apart). Nulls are expected; align everything by t_sec, not by row.",
                "Capture covers only the window the stream was running; it does NOT necessarily include cold start / key-on. To get the full trip, start capture.py BEFORE turning the key.",
                "Some channels read unsupported ceiling values (e.g. fuel trims at 99.2%, an O2 voltage pinned at 1.275V). Treat lone outliers skeptically.",
            ],
        },
        "parameters": params,
        "samples": samples,
    }
    out = args.out or os.path.splitext(args.input)[0] + ".json"
    json.dump(doc, open(out, "w"), indent=2)
    print(f"frames={len(frames)} params={len(params)} samples={len(samples)} "
          f"span={(str(min(ts)) + '..' + str(max(ts)) + 's') if ts else 'n/a'}")
    print(f"written -> {out}")


if __name__ == "__main__":
    main()
