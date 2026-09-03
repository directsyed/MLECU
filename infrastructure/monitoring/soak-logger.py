#!/usr/bin/env python3
"""soak-logger.py, unified PER-GPU thermal logger for the T630 GPU soak (MLECU).

Every INTERVAL seconds, writes one CSV row with per-GPU columns, combining three sources no single
tool covers on Linux:
  - gputemps (GDDR6X BAR0 reader)  -> per-GPU core / junction / VRAM   [needs root + iomem=relaxed]
  - nvidia-smi                     -> per-GPU power / SM clock / util
  - ipmitool sdr                   -> chassis fan RPM / CPU / inlet

Columns: timestamp, gpu<i>_core, gpu<i>_junc, gpu<i>_vram, gpu<i>_pwr (per detected GPU),
         sm_max, util_max, fan1_rpm, fan2_rpm, cpu_C, inlet_C, hottest

Run as root (gputemps + ipmitool need it):
    sudo ./soak-logger.py [outfile.csv] [interval_sec]
    sudo GPUTEMPS=/home/syed/gpu-tools/gputemps/gputemps ./soak-logger.py 3090ti-soak.csv 5

Auto-abort watches the HOTTEST card, so it protects whichever GPU the load lands on: if ANY GPU's
vram >= ABORT_VRAM (108C, GDDR6X 2C under its 110C ceiling), junction >= ABORT_JUNCTION (108C), or
core >= ABORT_CORE (90C), it forces the chassis fans to 100%, kills the load (KILL_PATTERNS), and
exits. All env-overridable. Junction/VRAM aborts need gputemps readable (iomem=relaxed); the logger
prints per-GPU armed/degraded status at startup.

Throttle signal: a GPU's sm clock dropping while its junction stays high = thermal throttle.
"""
import csv, json, os, re, subprocess, sys, time
from datetime import datetime

OUTFILE  = sys.argv[1] if len(sys.argv) > 1 else "soak-log.csv"
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
GPUTEMPS = os.environ.get("GPUTEMPS", "gputemps")
# --- auto-abort thresholds (env-overridable) ---
ABORT_VRAM     = float(os.environ.get("ABORT_VRAM", "108"))      # C; GDDR6X memory, 2C under its 110C ceiling
ABORT_JUNCTION = float(os.environ.get("ABORT_JUNCTION", "108"))  # C; GPU hotspot
ABORT_CORE     = float(os.environ.get("ABORT_CORE", "90"))       # C; edge, under the ~93C core shutdown
KILL_PATTERNS  = [p for p in os.environ.get("KILL_PATTERNS", "memtest_vulkan,gpu_burn").split(",") if p]


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def _num(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = re.search(r'-?\d+(?:\.\d+)?', x)
        return float(m.group()) if m else None
    return None


def gputemps_read():
    """Return {index: {'core','junction','vram'}} from `gputemps --once --json`. Shape:
    {"gpus":[{"index":0,"core":35,"junction":48,"vram":44}, ...]}. Per-GPU, so a 2-card
    chassis is fully visible (no collapsing to a single value)."""
    raw = run([GPUTEMPS, "--once", "--json"])
    out = {}
    for line in raw.strip().splitlines():
        try:
            obj = json.loads(line.strip())
        except Exception:
            continue
        gpus = obj.get("gpus") if isinstance(obj, dict) else (obj if isinstance(obj, list) else None)
        if not gpus:
            continue
        for g in gpus:
            if not isinstance(g, dict):
                continue
            idx = g.get("index")
            if idx is None:
                continue
            out[int(idx)] = {"core": _num(g.get("core")),
                             "junction": _num(g.get("junction")),
                             "vram": _num(g.get("vram"))}
    return out, raw.strip()


def nvsmi_read():
    """Return {index: {'temp','pwr','sm','util'}} across all GPUs."""
    out = run(["nvidia-smi",
               "--query-gpu=index,temperature.gpu,power.draw,clocks.sm,utilization.gpu",
               "--format=csv,noheader,nounits"])
    d = {}
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        d[idx] = {"temp": _num(parts[1]), "pwr": _num(parts[2]),
                  "sm": _num(parts[3]), "util": _num(parts[4])}
    return d


def ipmi_fans():
    f = {}
    for line in run(["ipmitool", "sdr", "type", "fan"]).splitlines():
        m = re.match(r'\s*(Fan\d)\b.*\|\s*(\d+)\s*RPM', line)
        if m:
            f[m.group(1)] = m.group(2)
    return f.get("Fan1", ""), f.get("Fan2", "")


def ipmi_temps():
    cpu = inlet = ""
    for line in run(["ipmitool", "sdr", "type", "temperature"]).splitlines():
        if "ok" not in line:
            continue
        m = re.search(r'(\d+)\s*degrees', line)
        if not m:
            continue
        if line.startswith("Inlet"):
            inlet = m.group(1)
        elif line.startswith("Temp") and not cpu:
            cpu = m.group(1)
    return cpu, inlet


def abort(reason):
    print(f"\n*** THERMAL ABORT: {reason} -> forcing fans 100%, killing load, exiting ***", file=sys.stderr)
    subprocess.run(["ipmitool", "raw", "0x30", "0x30", "0x01", "0x00"], capture_output=True)      # manual mode
    subprocess.run(["ipmitool", "raw", "0x30", "0x30", "0x02", "0xff", "0x64"], capture_output=True)  # fans 100%
    for pat in KILL_PATTERNS:
        subprocess.run(["pkill", "-f", pat], capture_output=True)
    sys.exit(2)


# ---- compact CONSOLE rendering (the CSV keeps the full-precision columns) -------------
# One narrow line per sample so it never wraps: HH:MM:SS + integer temps + short headers.
def _ci(v):
    """Integer cell for the console (rounds; '' for missing)."""
    if v is None or v == "":
        return ""
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)


def console_header(idxs):
    h = [f"{'time':<8}"]
    for i in idxs:
        h += [f"{str(i) + 'core':>5}", f"{str(i) + 'junc':>5}", f"{str(i) + 'vram':>5}", f"{str(i) + 'W':>4}"]
    h += [f"{'sm':>5}", f"{'fan1':>5}", f"{'fan2':>5}", f"{'cpu':>3}", f"{'inl':>3}"]
    return " ".join(h)


def console_line(ts, per, sm, f1, f2, cpu, inlet, idxs):
    parts = [f"{ts[-8:]:<8}"]   # HH:MM:SS (date is in the CSV; util is in the CSV too)
    for i in idxs:
        d = per.get(i, {})
        parts += [f"{_ci(d.get('core')):>5}", f"{_ci(d.get('junc')):>5}",
                  f"{_ci(d.get('vram')):>5}", f"{_ci(d.get('pwr')):>4}"]
    parts += [f"{_ci(sm):>5}", f"{_ci(f1):>5}", f"{_ci(f2):>5}", f"{_ci(cpu):>3}", f"{_ci(inlet):>3}"]
    return " ".join(parts)


def main():
    if os.geteuid() != 0:
        print("[warn] not root, gputemps & ipmitool will be blank; re-run with sudo", file=sys.stderr)
    gt, _ = gputemps_read()
    idxs = sorted(gt.keys()) or sorted(nvsmi_read().keys())
    if not idxs:
        print("[FATAL] no GPUs detected by gputemps or nvidia-smi", file=sys.stderr)
        sys.exit(1)

    gcols = []
    for i in idxs:
        gcols += [f"gpu{i}_core", f"gpu{i}_junc", f"gpu{i}_vram", f"gpu{i}_pwr"]
    COLS = ["timestamp"] + gcols + ["sm_max", "util_max", "fan1_rpm", "fan2_rpm", "cpu_C", "inlet_C", "hottest"]

    jmap = {i: gt.get(i, {}).get("junction") for i in idxs}
    if any(v is not None for v in jmap.values()):
        print(f"  [armed] per-GPU junction readable {jmap}; auto-abort on ANY card at "
              f"vram>={ABORT_VRAM}C / junction>={ABORT_JUNCTION}C / core>={ABORT_CORE}C")
    else:
        print(f"  [WARN] junction NOT readable on any GPU -> junction/VRAM abort INACTIVE "
              f"(core abort at {ABORT_CORE}C only, via nvidia-smi). Check iomem=relaxed + gputemps.",
              file=sys.stderr)

    write_header = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0
    with open(OUTFILE, "a", newline="") as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(COLS)
            fh.flush()
        hdr = console_header(idxs)
        rowc = 0
        while True:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            gt, _ = gputemps_read()
            ns = nvsmi_read()
            f1, f2 = ipmi_fans()
            cpu, inlet = ipmi_temps()

            row = [ts]
            per = {}
            worst_j = worst_v = worst_c = None
            hottest = ""
            sm_max = util_max = None
            for i in idxs:
                g = gt.get(i, {})
                nsi = ns.get(i, {})
                core = g.get("core") if g.get("core") is not None else nsi.get("temp")  # nvidia-smi core fallback
                junc = g.get("junction")
                vram = g.get("vram")
                pwr = nsi.get("pwr")
                per[i] = {"core": core, "junc": junc, "vram": vram, "pwr": pwr}
                row += [core if core is not None else "", junc if junc is not None else "",
                        vram if vram is not None else "", pwr if pwr is not None else ""]
                if junc is not None and (worst_j is None or junc > worst_j):
                    worst_j = junc
                    hottest = f"gpu{i}"
                if vram is not None and (worst_v is None or vram > worst_v):
                    worst_v = vram
                if core is not None and (worst_c is None or core > worst_c):
                    worst_c = core
                if nsi.get("sm") is not None:
                    sm_max = nsi["sm"] if sm_max is None else max(sm_max, nsi["sm"])
                if nsi.get("util") is not None:
                    util_max = nsi["util"] if util_max is None else max(util_max, nsi["util"])
            row += [sm_max if sm_max is not None else "", util_max if util_max is not None else "",
                    f1, f2, cpu, inlet, hottest]
            w.writerow(row)
            fh.flush()
            if rowc % 20 == 0:
                print(hdr)     # re-echo the header periodically so labels stay in view
            rowc += 1
            print(console_line(ts, per, sm_max, f1, f2, cpu, inlet, idxs))

            if worst_v is not None and worst_v >= ABORT_VRAM:
                abort(f"vram {worst_v}C >= {ABORT_VRAM}C (hottest {hottest})")
            if worst_j is not None and worst_j >= ABORT_JUNCTION:
                abort(f"junction {worst_j}C >= {ABORT_JUNCTION}C (hottest {hottest})")
            if worst_c is not None and worst_c >= ABORT_CORE:
                abort(f"core {worst_c}C >= {ABORT_CORE}C")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
