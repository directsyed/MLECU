"""Offload calibration — find each model's max-capability serving config (Syed, 2026-07-30).

WHY: `--tensor-split 3.5,1` allocates LAYERS, so the 3090's VRAM occupancy is tied to its
compute duty. On the 35B that left 16.9 GiB of 3090 VRAM idle while 8.4 GiB of expert
weights streamed from RAM at ~8x lower bandwidth. Syed's directive: run every model to the
maximum the underpowered card allows, rather than leaving VRAM unused.

HOW: `--override-tensor` (-ot) places tensors by regex on a named device, independent of the
layer split. Expert tensors are `blk.N.ffn_{down,gate,up}_exps.weight`, ~0.8 GiB per layer,
so we can hand a chosen band of layers' experts to CUDA1 (the 3090) and push the remainder
to CPU, while attention/shared layers follow the normal split.

THE SAFETY ARGUMENT, measured not assumed: the 3090 is clock-locked at 810 MHz, and that
lock — not the split — is the real power ceiling (117 W at 22% duty; historical peak ~171 W
at higher duty; 230 W is what killed the box, and is unreachable at this clock). This script
therefore SWEEPS candidate configs under real sustained load and picks the most aggressive
one whose sustained 3090 draw stays inside the proven-safe band. A config is rejected the
moment it exceeds POWER_ACCEPT, and the sweep stops.

Run: car/.venv/bin/python -m bench.calibrate <model_key>
Writes the winning profile into the ledger for that model's remaining units.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

from . import ledger
from .driver import (MLECU, gpu_power, log, server_start, server_stop, VENV, EVAL_DIR)

POWER_ACCEPT = 165.0     # sustained mean must stay at/below the proven-safe operating band
POWER_HARD = 185.0       # any single sample above this rejects the config outright
SAMPLE_S = 2
PROBE_CASES = 6          # enough sustained decode to load the card honestly


def expert_layers(gguf: Path) -> tuple[int, float]:
    """(n_layers_with_experts, GiB per layer) read from the GGUF itself."""
    from gguf import GGUFReader
    r = GGUFReader(str(gguf))
    per = {}
    for t in r.tensors:
        if "exps" in t.name:
            m = re.match(r"blk\.(\d+)\.", t.name)
            if m:
                per[int(m.group(1))] = per.get(int(m.group(1)), 0) + t.n_bytes
    if not per:
        return 0, 0.0
    return len(per), (sum(per.values()) / len(per)) / 2**30


def ot_flag(lo: int, hi: int, device: str = "CUDA1") -> list[str]:
    """Pin experts of layers [lo,hi] to `device`. Regex must match llama.cpp tensor names."""
    rng = "|".join(str(i) for i in range(lo, hi + 1))
    return ["-ot", f"blk\\.({rng})\\.ffn_.*_exps\\.weight={device}"]


def measure(profile: dict) -> dict | None:
    """Start the server on `profile`, drive real decode, sample 3090 power. None if it fails."""
    if not server_start(profile):
        return None
    watts: list[float] = []
    t0 = time.time()
    p = subprocess.Popen(
        [str(VENV), "-m", "harness.cli", "--run-e1", "--arm", "A", "--runs", "1",
         "--limit", str(PROBE_CASES), "--cases", "data/sim_cases_v2.jsonl",
         "--model-name", "CALIB|throwaway"],
        cwd=str(EVAL_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    while p.poll() is None:
        time.sleep(SAMPLE_S)
        w = gpu_power(1)
        if w > 0:
            watts.append(w)
        if w > POWER_HARD:
            log(f"  CALIB: {w:.0f}W exceeds hard limit {POWER_HARD} — aborting config")
            p.kill()
            server_stop()
            return {"rejected": True, "peak": w, "mean": statistics.mean(watts)}
    elapsed = time.time() - t0
    if not watts:
        return None
    return {"rejected": False, "mean": statistics.mean(watts), "peak": max(watts),
            "elapsed_s": round(elapsed, 1)}


def _cleanup_calib_results() -> None:
    for f in (EVAL_DIR / "results").glob("e1-armA-*.jsonl"):
        try:
            first = json.loads(f.open().readline())
            if first.get("model") == "CALIB|throwaway":
                f.unlink()
        except Exception:
            pass


def calibrate(model_key: str) -> dict | None:
    """Sweep expert-band sizes from conservative to aggressive; keep the best safe one."""
    with ledger.connect() as c:
        row = c.execute("SELECT server_profile FROM unit WHERE model_key=? LIMIT 1",
                        (model_key,)).fetchone()
    if not row:
        log(f"CALIB: no units for {model_key}")
        return None
    base = json.loads(row["server_profile"])
    gguf = Path(base["gguf"])
    n_layers, gib = expert_layers(gguf)
    if not n_layers:
        log(f"CALIB: {model_key} has no expert tensors (dense) — nothing to tune")
        return None
    # how many layers' experts fit in the 3090's usable VRAM (leave 3 GiB for KV/buffers)
    budget = 21.0
    max_layers = max(0, min(n_layers, int(budget / gib)))
    log(f"CALIB {model_key}: {n_layers} expert layers x {gib:.2f} GiB; "
        f"3090 could host up to {max_layers}")

    # POLICY (Syed 2026-07-30): fill the HEALTHY Ti first, spill only the remainder onto the
    # convicted 3090. The first calibration did the opposite — proportional splitting left
    # the 3090 holding 21.7 GiB against the Ti's 15.0, i.e. the failure-prone card carrying
    # the larger share. Now tensor_split="1,0" sends everything to the Ti and -ot moves the
    # minimum number of expert layers needed to make it fit.
    model_gib = gguf.stat().st_size / 2**30
    TI_USABLE = 21.0            # 24.5 minus KV cache + compute buffers
    n_min = max(0, int((model_gib - TI_USABLE) / gib) + 1)
    ladder = [n for n in (n_min, n_min + 3, n_min + 6, max_layers) if 0 < n <= max_layers]
    log(f"CALIB: Ti-first policy — minimum 3090 band = {n_min} layers "
        f"({n_min*gib:.1f} GiB of a {model_gib:.1f} GiB model)")

    best = None
    for n in ladder:
        prof = dict(base)
        prof["key"] = f"{model_key}-ot{n}"
        # DROP -ncmoe: it and -ot are competing placement policies. Keeping both left 8 GiB
        # of experts on the CPU while the -ot band moved to the 3090 — total VRAM residency
        # was unchanged, defeating the point (observed 2026-07-30, first calibration run).
        # -ot places the 3090's band explicitly; everything else follows the tensor split,
        # and only what genuinely cannot fit spills to RAM.
        keep = []
        skip_next = False
        for tok in base.get("extra", []):
            if skip_next:
                skip_next = False
                continue
            if tok in ("-ncmoe", "--n-cpu-moe"):
                skip_next = True
                continue
            keep.append(tok)
        prof["extra"] = keep + ot_flag(0, n - 1)
        prof["tensor_split"] = "1,0"      # everything to the Ti; -ot places the overflow
        log(f"CALIB: trying {n} layers of experts on the 3090 ({n*gib:.1f} GiB)")
        m = measure(prof)
        _cleanup_calib_results()
        if m is None:
            log(f"  -> failed to load/run; trying smaller")
            continue
        log(f"  -> mean {m['mean']:.0f}W peak {m['peak']:.0f}W "
            f"{'REJECTED' if m['rejected'] else ''}")
        if not m["rejected"] and m["mean"] <= POWER_ACCEPT:
            best = {"profile": prof, "metrics": m, "layers": n}
            break          # sweep runs most-aggressive-first, so the first pass is the best
    server_stop()
    if best is None:
        log(f"CALIB {model_key}: no config met the power budget — keeping original profile")
        return None
    with ledger.connect() as c:
        cur = c.execute("UPDATE unit SET server_profile=? WHERE model_key=? AND state='pending'",
                        (json.dumps(best["profile"]), model_key))
        c.commit()
    ledger.set_meta(f"calib.{model_key}", json.dumps(
        {"layers_on_3090": best["layers"], **best["metrics"]}))
    log(f"CALIB {model_key}: ADOPTED {best['layers']} expert layers on the 3090 "
        f"(mean {best['metrics']['mean']:.0f}W) -> {cur.rowcount} pending units updated")
    return best


if __name__ == "__main__":
    ledger.init()
    calibrate(sys.argv[1])
