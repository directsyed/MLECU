"""Autonomous benchmark driver — claims ledger units and executes them (2026-07-29).

Runs unattended for days under `systemd --user`. Everything it does is recoverable: if the
box dies (the 3090 has done it 11 times), systemd restarts this, `reset_running()` returns
the interrupted unit to pending, and the loop picks up where it stopped.

SAFETY (the part that matters most): the 3090's proven-safe envelope is ~152W; 230W is
proven fatal to the WHOLE MACHINE. That envelope was validated for a dense 27B at a 3.5:1
layer split — with `-ncmoe` expert offload the per-layer cost changes, so the split fraction
no longer implies the wattage. Therefore the guarantee here is a MEASURED one: sample GPU1
power every 5s, and on a sustained excursion kill the server, re-queue the model on its
Ti-only profile, and log it. The flag is a proxy; the watt meter is the truth.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from . import ledger

MLECU = Path(__file__).resolve().parents[3]
EVAL_DIR = MLECU / "ml/eval"
VENV = MLECU / "car/.venv/bin/python"
JUDGE_VENV = MLECU / "ml/curation/.venv/bin/python"
LLS = Path("/home/syed/tools/llama.cpp/build/bin/llama-server")
LOG = MLECU / "ml/finetuning/logs/bench-driver.log"
SRVLOG = MLECU / "ml/finetuning/logs/bench-server.log"
INDEX = EVAL_DIR / "data/ref_dense_v1.npz"

# --- 3090 duty guard -------------------------------------------------------
# CALIBRATED against the real envelope, not guessed (smoke test 2026-07-29):
#   proven SAFE   = the dense-27B 3.5:1 config, 8+ days crash-free. Typical ~152W, but it
#                   transiently touches 171W — measured during the smoke run. A 170W
#                   ceiling would therefore false-trip on KNOWN-GOOD operation.
#   proven FATAL  = ~230W sustained decode (crashes #10/#11).
# 200W sits above the safe config's transient peaks and well below the fatal level; the
# 3-sample rule means only a SUSTAINED 15s excursion trips it, since the failure mode is
# sustained load rather than momentary spikes.
GPU1_WATT_CEILING = 200.0
GPU1_TRIPS_TO_ABORT = 3       # consecutive 5s samples above ceiling => 15s sustained
WATCH_INTERVAL_S = 5

# --- car-data preemption ---------------------------------------------------
CAR_WATCH = [MLECU / "car/dataset", MLECU / "car/ecu/rom-archive"]
CAR_GLOBS = ["*.csv", "*.bin"]

MIN_FREE_GB = 80
_server_proc: subprocess.Popen | None = None
_server_key = ""


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%F %T')}] {msg}"
    with LOG.open("a") as f:
        f.write(line + "\n")
    print(line, flush=True)


# ---------------------------------------------------------------- gpu / server

def gpu_power(idx: int) -> float:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={idx}", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        return float(out.splitlines()[0])
    except Exception:
        return 0.0


def gpu_mem_used(idx: int) -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={idx}", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        return int(out.splitlines()[0])
    except Exception:
        return 0


def clocks_locked() -> bool:
    """The 3090's clock lock is its only protection. Verify, and self-heal if it drifted
    (the NOPASSWD sudoers entry exists precisely for this)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,clocks.gr,clocks.max.gr",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15).stdout
        # GPU1 = the convicted 3090; must be pinned at 800MHz
        for line in out.strip().splitlines():
            idx, cur, _mx = [x.strip() for x in line.split(",")]
            if idx == "1" and int(cur) > 900:
                log(f"WARNING: 3090 clock drifted to {cur}MHz — re-applying lock")
                subprocess.run(["sudo", "-n", "nvidia-smi", "-i", "1", "-lgc", "800,800"],
                               capture_output=True, timeout=30)
                return False
        return True
    except Exception as e:
        log(f"clock check failed: {e}")
        return True          # don't halt the pipeline on a transient nvidia-smi hiccup


def server_stop() -> None:
    """Stop OUR server only. The pkill pattern is deliberately narrow: the old chain's
    pattern also matched llama-judge, which has Restart=on-failure and would fight us."""
    global _server_proc, _server_key
    if _server_proc and _server_proc.poll() is None:
        _server_proc.send_signal(signal.SIGTERM)
        try:
            _server_proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            _server_proc.kill()
    _server_proc, _server_key = None, ""
    # VRAM-release verification — without this the next (larger) model OOMs at load
    for _ in range(60):
        if gpu_mem_used(0) < 1500 and gpu_mem_used(1) < 1500:
            break
        time.sleep(5)
    else:
        log("WARNING: VRAM did not fully release after server stop")
    log("server stopped, VRAM released")


def server_start(profile: dict) -> bool:
    """profile: {key, gguf, extra:[flags], ti_only:bool}. Health-polls up to 20 min
    (a 65GB model over expert-offload loads slowly)."""
    global _server_proc, _server_key
    if _server_key == profile["key"] and _server_proc and _server_proc.poll() is None:
        return True                                   # already serving this exact profile
    server_stop()
    gguf = Path(profile["gguf"])
    if not gguf.exists():
        log(f"server_start: GGUF missing {gguf}")
        return False
    cmd = [str(LLS), "-m", str(gguf), "-ngl", "999", "-c", "16384", "-np", "1",
           "--host", "127.0.0.1", "--port", "8080", "--jinja"]
    if profile.get("ti_only"):
        cmd += ["--split-mode", "none", "--main-gpu", "0"]
    else:
        cmd += ["--split-mode", "layer", "--tensor-split", "3.5,1"]
    cmd += profile.get("extra", [])
    SRVLOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if profile.get("ti_only"):
        env["CUDA_VISIBLE_DEVICES"] = "0"
    with SRVLOG.open("a") as sf:
        sf.write(f"\n===== {time.strftime('%F %T')} {profile['key']} :: {' '.join(cmd)}\n")
        _server_proc = subprocess.Popen(cmd, stdout=sf, stderr=subprocess.STDOUT, env=env)
    _server_key = profile["key"]
    log(f"server[{profile['key']}] starting (pid {_server_proc.pid})")
    for _ in range(120):                              # 120 x 10s = 20 min
        time.sleep(10)
        if _server_proc.poll() is not None:
            log(f"server[{profile['key']}] DIED during load (exit {_server_proc.returncode})")
            _server_key = ""
            return False
        try:
            r = subprocess.run(["curl", "-sf", "http://127.0.0.1:8080/v1/models"],
                               capture_output=True, timeout=10)
            if r.returncode == 0:
                log(f"server[{profile['key']}] healthy")
                return True
        except Exception:
            pass
    log(f"server[{profile['key']}] health TIMEOUT")
    server_stop()
    return False


# ---------------------------------------------------------------- preemption

def car_data_present() -> list[Path]:
    hits: list[Path] = []
    for d in CAR_WATCH:
        if d.exists():
            for g in CAR_GLOBS:
                hits += list(d.glob(g))
    return hits


def preflight() -> tuple[bool, str]:
    free_gb = shutil.disk_usage(MLECU).free / 1e9
    if free_gb < MIN_FREE_GB:
        return False, f"disk low: {free_gb:.0f}GB free"
    if not INDEX.exists():
        return False, "dense index missing — refusing to run hybrid cells on BM25 fallback"
    for mc in sorted(Path("/sys/devices/system/edac/mc").glob("mc*")):
        for kind in ("ce_count", "ue_count"):
            f = mc / kind
            if f.exists() and int(f.read_text().strip() or 0) > 0:
                return False, f"ECC {kind} nonzero on {mc.name} — halting for Syed"
    clocks_locked()
    return True, "ok"


# ---------------------------------------------------------------- execution

def run_unit(unit) -> None:
    argv = json.loads(unit["argv_json"])
    kind = unit["kind"]
    log(f"UNIT {unit['id']} [{unit['phase']}/{unit['label']}] kind={kind}")

    if kind == "shell":
        rc, note = _run_shell(argv, unit)
        if rc == 0:
            ledger.mark_done(unit["id"], note=note)
        else:
            ledger.mark_failed(unit["id"], f"exit {rc}: {note}")
        return

    # harness unit — needs a server
    profile = json.loads(unit["server_profile"]) if unit["server_profile"] else None
    if profile and not Path(profile["gguf"]).exists():
        # Model still downloading. DEFER (back to pending), don't fail — otherwise a slow
        # download would burn every unit of that model before its file lands.
        ledger.requeue(unit["id"], "deferred: model file not yet present")
        log(f"  deferring {unit['label']}: {Path(profile['gguf']).name} not on disk yet")
        time.sleep(600)
        return
    if profile and not server_start(profile):
        ledger.mark_failed(unit["id"], "server failed to start")
        return

    before = _existing_results()
    rc, watchdog_trip = _run_harness(argv)
    out = _new_result(before)

    if watchdog_trip:
        ledger.mark_failed(unit["id"], "3090 duty excursion — see driver log")
        log("DUTY TRIP: re-queueing this model on its Ti-only profile")
        _fallback_to_ti_only(unit)
        return
    if rc != 0:
        ledger.mark_failed(unit["id"], f"harness exit {rc}", out_path=str(out) if out else "")
        return
    if out is None:
        ledger.mark_failed(unit["id"], "no result file produced")
        return
    ok, msg = ledger.validate_output(out, unit["model_tag"], unit["n_rows_expected"], unit["arm"])
    n = sum(1 for _ in out.open())
    if ok:
        ledger.mark_done(unit["id"], out_path=str(out), n_rows_got=n, note=msg)
        log(f"  -> done: {msg}")
    else:
        ledger.mark_failed(unit["id"], msg, out_path=str(out), n_rows_got=n)
        log(f"  -> FAILED validation: {msg}")


def _run_shell(argv: list[str], unit) -> tuple[int, str]:
    p = subprocess.run(argv[0], shell=True, capture_output=True, text=True, cwd=str(MLECU))
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    return p.returncode, " | ".join(tail)[:500]


def _run_harness(argv: list[str]) -> tuple[int, bool]:
    """Run a harness.cli invocation with the duty watchdog sampling alongside it."""
    cmd = [str(VENV), "-m", "harness.cli"] + argv
    p = subprocess.Popen(cmd, cwd=str(EVAL_DIR), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    trips = 0
    trip = False
    while p.poll() is None:
        time.sleep(WATCH_INTERVAL_S)
        w = gpu_power(1)
        if w > GPU1_WATT_CEILING:
            trips += 1
            log(f"  3090 duty {w:.0f}W (>{GPU1_WATT_CEILING}) trip {trips}/{GPU1_TRIPS_TO_ABORT}")
            if trips >= GPU1_TRIPS_TO_ABORT:
                trip = True
                p.kill()
                server_stop()
                break
        else:
            trips = 0
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill()
    return (p.returncode if p.returncode is not None else 1), trip


def _fallback_to_ti_only(unit) -> None:
    """A duty excursion means this model's dual-GPU profile is unsafe. Re-queue every
    remaining unit of the model with the 3090 removed from the picture entirely."""
    with ledger.connect() as c:
        rows = c.execute("SELECT id, server_profile FROM unit WHERE model_key=? AND "
                         "state IN ('pending','failed')", (unit["model_key"],)).fetchall()
        for r in rows:
            prof = json.loads(r["server_profile"]) if r["server_profile"] else {}
            prof["ti_only"] = True
            prof["key"] = prof.get("key", "") + "-tionly"
            c.execute("UPDATE unit SET state='pending', server_profile=?, "
                      "note='ti-only fallback after duty trip' WHERE id=?",
                      (json.dumps(prof), r["id"]))
        c.commit()
    log(f"  re-queued {len(rows)} units of {unit['model_key']} as Ti-only")


def _existing_results() -> set:
    return {p.name for p in (EVAL_DIR / "results").glob("e*.jsonl")}


def _new_result(before: set) -> Path | None:
    new = [p for p in (EVAL_DIR / "results").glob("e*.jsonl") if p.name not in before]
    return max(new, key=lambda p: p.stat().st_mtime) if new else None


# ---------------------------------------------------------------- main loop

def main() -> None:
    ledger.init()
    n = ledger.reset_running()
    if n:
        log(f"recovered {n} unit(s) left running by a previous driver death")
    log("=== driver start ===")
    while True:
        if ledger.get_meta("paused") == "1":
            log("paused (meta) — sleeping 300s")
            time.sleep(300)
            continue
        hits = car_data_present()
        if hits:
            log(f"CAR DATA DETECTED: {[h.name for h in hits][:4]} — hard preempt")
            server_stop()
            ledger.set_meta("paused", "1")
            ledger.set_meta("pause_reason", f"car-data drop: {[str(h) for h in hits][:4]}")
            continue
        ok, why = preflight()
        if not ok:
            log(f"PREFLIGHT HALT: {why}")
            ledger.set_meta("paused", "1")
            ledger.set_meta("pause_reason", why)
            continue
        unit = ledger.claim_next()
        if unit is None:
            log("no pending units — all phases drained. Stopping server and exiting.")
            server_stop()
            ledger.set_meta("finished_at", time.strftime("%F %T"))
            return
        try:
            run_unit(unit)
        except Exception as e:                       # never let one unit kill the driver
            log(f"UNIT EXCEPTION {unit['id']}: {e!r}")
            ledger.mark_failed(unit["id"], f"driver exception: {e!r}")


if __name__ == "__main__":
    main()
