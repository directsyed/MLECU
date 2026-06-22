#!/usr/bin/env python3
"""soak-logger.py — unified thermal logger for the T630 GPU soak (MLECU).

Every INTERVAL seconds, writes one CSV row combining three sources that no single
tool covers on Linux:
  - gputemps (gddr6 BAR0 reader)  -> core / junction / VRAM   [needs root + iomem=relaxed]
  - nvidia-smi                    -> core(fallback) / power / SM clock / util
  - ipmitool sdr                  -> chassis fan RPM / CPU / inlet

Columns: timestamp, core_C, junction_C, vram_C, power_W, sm_MHz, util_pct,
         fan1_rpm, fan2_rpm, cpu_C, inlet_C

Run as root (gputemps + ipmitool need it):
    sudo ./soak-logger.py [outfile.csv] [interval_sec]
If gputemps isn't on PATH:  sudo GPUTEMPS=/path/to/gputemps ./soak-logger.py ...

Throttle signal: watch sm_MHz — a sustained clock drop while junction is high = thermal throttle.
"""
import csv, json, os, re, subprocess, sys, time
from datetime import datetime

OUTFILE  = sys.argv[1] if len(sys.argv) > 1 else "soak-log.csv"
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
GPUTEMPS = os.environ.get("GPUTEMPS", "gputemps")
COLS = ["timestamp","core_C","junction_C","vram_C","power_W","sm_MHz",
        "util_pct","fan1_rpm","fan2_rpm","cpu_C","inlet_C"]

def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""

def _flatten(obj, out):
    """Collect every numeric leaf as {lowercased_key: number} — tolerant of gputemps' JSON shape."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)): _flatten(v, out)
            elif isinstance(v, bool): pass
            elif isinstance(v, (int, float)): out[str(k).lower()] = v
            elif isinstance(v, str):
                m = re.search(r'-?\d+(?:\.\d+)?', v)
                if m: out[str(k).lower()] = float(m.group())
    elif isinstance(obj, list):
        for it in obj: _flatten(it, out)

def gputemps_read():
    raw = run([GPUTEMPS, "--once", "--json"])
    flat = {}
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if not line: continue
        try:
            cand = {}; _flatten(json.loads(line), cand)
            if cand: flat = cand; break
        except Exception:
            continue
    def pick(subs):
        for name, val in flat.items():
            if any(s in name for s in subs): return val
        return ""
    return pick(["core","edge"]), pick(["junc","hot","spot"]), pick(["vram","mem"]), raw.strip()

def nvsmi_read():
    out = run(["nvidia-smi",
               "--query-gpu=temperature.gpu,power.draw,clocks.sm,utilization.gpu",
               "--format=csv,noheader,nounits"]).strip()
    parts = [p.strip() for p in out.splitlines()[0].split(",")] if out else []
    parts += [""] * (4 - len(parts))
    return parts[0], parts[1], parts[2], parts[3]

def ipmi_fans():
    f = {}
    for line in run(["ipmitool","sdr","type","fan"]).splitlines():
        m = re.match(r'\s*(Fan\d)\b.*\|\s*(\d+)\s*RPM', line)
        if m: f[m.group(1)] = m.group(2)
    return f.get("Fan1",""), f.get("Fan2","")

def ipmi_temps():
    cpu = inlet = ""
    for line in run(["ipmitool","sdr","type","temperature"]).splitlines():
        if "ok" not in line: continue
        m = re.search(r'(\d+)\s*degrees', line)
        if not m: continue
        if line.startswith("Inlet"): inlet = m.group(1)
        elif line.startswith("Temp") and not cpu: cpu = m.group(1)
    return cpu, inlet

def main():
    if os.geteuid() != 0:
        print("[warn] not root — gputemps & ipmitool will be blank; re-run with sudo", file=sys.stderr)
    write_header = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0
    with open(OUTFILE, "a", newline="") as fh:
        w = csv.writer(fh)
        if write_header: w.writerow(COLS); fh.flush()
        print("  ".join(COLS))
        while True:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            core, junc, vram, raw = gputemps_read()
            t_core, power, sm, util = nvsmi_read()
            f1, f2 = ipmi_fans()
            cpu, inlet = ipmi_temps()
            row = [ts, core or t_core, junc, vram, power, sm, util, f1, f2, cpu, inlet]
            w.writerow(row); fh.flush()
            print("  ".join(str(x) for x in row))
            if junc == "":
                print(f"  [warn] no junction temp parsed; gputemps raw: {raw[:160]!r}", file=sys.stderr)
            time.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
