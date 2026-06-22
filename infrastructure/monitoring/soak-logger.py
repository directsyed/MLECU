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

Auto-abort: if vram >= ABORT_VRAM (default 108C; the GDDR6X memory temp, nearest its 110C ceiling),
junction >= ABORT_JUNCTION (108C; GPU hotspot), or core >= ABORT_CORE (90C; edge), it forces the
chassis fans to 100%, kills the load (KILL_PATTERNS, default "memtest_vulkan,gpu_burn"), and exits.
All env-overridable. NOTE: the vram/junction aborts only work once gputemps can read them (needs
iomem=relaxed); the logger warns at startup if it can't.

Throttle signal: watch sm_MHz — a sustained clock drop while junction is high = thermal throttle.
"""
import csv, json, os, re, subprocess, sys, time
from datetime import datetime

OUTFILE  = sys.argv[1] if len(sys.argv) > 1 else "soak-log.csv"
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
GPUTEMPS = os.environ.get("GPUTEMPS", "gputemps")
# --- auto-abort thresholds (env-overridable) ---
ABORT_VRAM     = float(os.environ.get("ABORT_VRAM", "108"))      # C; GDDR6X memory — 2C under its 110C ceiling (the one nearest the limit)
ABORT_JUNCTION = float(os.environ.get("ABORT_JUNCTION", "108"))  # C; GPU hotspot
ABORT_CORE     = float(os.environ.get("ABORT_CORE", "90"))       # C; edge, under the ~93C core shutdown
KILL_PATTERNS  = [p for p in os.environ.get("KILL_PATTERNS", "memtest_vulkan,gpu_burn").split(",") if p]
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

def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def abort(reason):
    print(f"\n*** THERMAL ABORT: {reason} -> forcing fans 100%, killing load, exiting ***", file=sys.stderr)
    subprocess.run(["ipmitool","raw","0x30","0x30","0x01","0x00"], capture_output=True)   # ensure manual mode
    subprocess.run(["ipmitool","raw","0x30","0x30","0x02","0xff","0x64"], capture_output=True)  # all fans 100%
    for pat in KILL_PATTERNS:
        subprocess.run(["pkill","-f",pat], capture_output=True)
    sys.exit(2)

def main():
    if os.geteuid() != 0:
        print("[warn] not root — gputemps & ipmitool will be blank; re-run with sudo", file=sys.stderr)
    write_header = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0
    with open(OUTFILE, "a", newline="") as fh:
        w = csv.writer(fh)
        if write_header: w.writerow(COLS); fh.flush()
        print("  ".join(COLS))
        _, j0, _, _ = gputemps_read()
        if _f(j0) is None:
            print(f"  [WARN] junction NOT readable -> JUNCTION abort INACTIVE (only core abort at "
                  f"{ABORT_CORE}C live). Fix iomem=relaxed + build gputemps before a VRAM soak.", file=sys.stderr)
        else:
            print(f"  [armed] junction readable (idle {j0}C); auto-abort at vram>={ABORT_VRAM}C / junction>={ABORT_JUNCTION}C / core>={ABORT_CORE}C")
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
            jv, vv, cv = _f(junc), _f(vram), _f(core or t_core)
            if vv is not None and vv >= ABORT_VRAM:     abort(f"vram {vv}C >= {ABORT_VRAM}C")
            if jv is not None and jv >= ABORT_JUNCTION: abort(f"junction {jv}C >= {ABORT_JUNCTION}C")
            if cv is not None and cv >= ABORT_CORE:     abort(f"core {cv}C >= {ABORT_CORE}C")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
