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


def shard_files(gguf: Path) -> list[Path]:
    """All shards of a split GGUF, or just the file itself.

    Bug this fixes (found by dry-run 2026-07-30): globbing the parent directory for *.gguf
    summed UNRELATED models that share a directory (the 35B read as 83.6 GiB because the
    27B Q6 and Q8 sit beside it), and reading only shard 1 undercounted expert tensors on
    split models (Mistral reported zero expert layers -> divide-by-zero)."""
    m = re.match(r"(.*)-(\d{5})-of-(\d{5})\.gguf$", gguf.name)
    if m:
        return sorted(gguf.parent.glob(f"{m.group(1)}-*-of-{m.group(3)}.gguf"))
    return [gguf]


def model_size_gib(gguf: Path) -> float:
    return sum(f.stat().st_size for f in shard_files(gguf)) / 2**30


def expert_layers(gguf: Path) -> tuple[int, float]:
    """(n_layers_with_experts, GiB per layer), summed across ALL shards."""
    from gguf import GGUFReader
    per: dict[int, int] = {}
    for shard in shard_files(gguf):
        try:
            r = GGUFReader(str(shard))
        except Exception:
            continue
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
        # MUST filter to a harness unit with a real profile: the calib unit itself has an
        # EMPTY server_profile, and an unfiltered LIMIT 1 returns whichever row sorts first.
        # Earlier models only worked by accident of insertion order; the 80B-Thinking's calib
        # unit was inserted first and json.loads('') threw, so the driver ran its cells
        # UNCALIBRATED (2026-07-31).
        row = c.execute("SELECT server_profile FROM unit WHERE model_key=? AND kind='harness' "
                        "AND server_profile IS NOT NULL AND server_profile != '' LIMIT 1",
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

    # POLICY (Syed 2026-07-30): fill the HEALTHY Ti first; the convicted 3090 takes only what
    # it must. TWO REGIMES, because a single rule breaks on oversized models (found live:
    # the 80B is 61 GiB, so tensor_split="1,0" demanded 41 GiB from a 24.5 GiB Ti and every
    # candidate config failed to load):
    #   FITS   (model + KV <= combined VRAM): MINIMISE the 3090 band — the Ti absorbs the
    #           rest for free, so less on the convicted card costs nothing.
    #   OVERSIZED: the remainder must go to RAM regardless, so MAXIMISE the 3090 band within
    #           the power budget — every GiB there is a GiB not streaming at 8x lower
    #           bandwidth. Ti still fills first; RAM takes only the genuine overflow.
    # Sharded GGUFs: size is the sum of all shards, not just shard 1.
    model_gib = model_size_gib(gguf)
    TI_USABLE = 21.0            # 24.5 minus KV cache + compute buffers
    non_expert = max(0.0, model_gib - n_layers * gib)
    ti_expert_layers = max(0, int((TI_USABLE - non_expert) / gib))
    fits = model_gib + 3.0 <= 45.0

    if fits:
        n_min = max(0, int((model_gib - TI_USABLE) / gib) + 1)
        ladder = [n for n in (n_min, n_min + 3, n_min + 6, max_layers) if 0 < n <= max_layers]
        cpu_from = None
        log(f"CALIB: FITS regime — minimise 3090; min band {n_min} layers "
            f"({n_min*gib:.1f} GiB of {model_gib:.1f} GiB)")
    else:
        ladder = [n for n in (max_layers, int(max_layers * 0.7), int(max_layers * 0.45))
                  if n > 0]
        cpu_from = ti_expert_layers        # set per-candidate below
        log(f"CALIB: OVERSIZED regime — {model_gib:.1f} GiB > VRAM. non-expert "
            f"{non_expert:.1f} GiB; Ti takes {ti_expert_layers} expert layers; "
            f"maximise 3090 band then RAM takes the rest")

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
        if not fits:
            # three-way: [0,n) -> 3090, [n, n+ti_expert_layers) -> Ti via the 1,0 split,
            # everything above that -> CPU. Without the explicit CPU band the Ti OOMs.
            cpu_start = n + ti_expert_layers
            if cpu_start < n_layers:
                prof["extra"] = prof["extra"] + ot_flag(cpu_start, n_layers - 1, "CPU")
                log(f"    layout: 3090 layers 0-{n-1} ({n*gib:.1f} GiB) | "
                    f"Ti {ti_expert_layers} layers + {non_expert:.1f} GiB non-expert | "
                    f"CPU layers {cpu_start}-{n_layers-1} "
                    f"({(n_layers-cpu_start)*gib:.1f} GiB)")
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
