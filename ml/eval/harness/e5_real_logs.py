"""E5, blind diagnosis from REAL car logs. The first time this project shows the model
data that came off the actual engine.

WHY IT EXISTS. Every LLM call in this repo up to now has been synthetic: E1/E2/E4 build their
numbers from the MVEM simulator, and `e4.py:383` says so outright ("Real diagnosis runs through
logparse.observe, not this sim"). Meanwhile the deterministic side does read real logs, and
`car/ecutune/cli.py:131` says the other half of it: "Claude does not read the logs here --
identify() does." So the bridge between real logs and the model was named in two places and
built in neither. This is that bridge.

WHAT IS BEING TESTED. Between 2026-08-26 and 08-27 six vacuum drives established, by hand and
then independently by the deterministic stage, that this car's MAF under-reports airflow
progressively above ~10 g/s. The question here is whether the local model reaches the same
conclusion from the same evidence, WITHOUT being told.

The discrimination is sharp, and it is the one that matters for this car. `FAULT_IDS` already
contains both live hypotheses:
    maf_low      -- believed/true transfer < 1, i.e. the sensor reads low   <- ground truth
    vacuum_leak  -- unmetered air past the sensor                            <- the confound
Syed's MAF-to-turbo tubing is custom and a leak there produces a similar trim signature, so
this is not a straw-man distractor: it is the alternative we genuinely cannot rule out from
logs alone. A model that says `vacuum_leak` is not obviously wrong -- but the flow-dependent
SHAPE of the error is the evidence that separates them, and whether the model uses that shape
is exactly what we want to know.

TWO ARMS, TWO INPUT TREATMENTS (Syed's call, 2026-08-27):
  arm 1  forced choice, grammar-constrained to FAULT_IDS -- scorable
  arm 2  open-ended, no schema -- read qualitatively; can it describe a curve, which no enum can
  input A  derived summary tables (what a tuner would look at)
  input B  sampled raw CSV rows (does it aggregate for itself)

HONESTY RULES, because this is a blind trial and it is trivial to accidentally cheat:
  * The prompts are built ONLY from log-derived numbers. Nothing mentions MAF calibration,
    the conclusion, or the correction curve.
  * `car/logging/drive/ANALYSIS-2026-08-26-vacuum-drives.md` and decisions.md D21 hold the
    ground truth. They are used for SCORING and are never shown to the model.
  * Per `ml/CLAUDE.md`, whatever the model produces gets a Claude review pass before it counts
    for anything, and its numbers never reach a ROM.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
CAR = REPO / "car"
if str(CAR) not in sys.path:
    sys.path.insert(0, str(CAR))

from ecutune.evals.faults import FAULT_IDS          # noqa: E402
from ecutune.logparse.romraider_csv import parse_romraider_csv   # noqa: E402
from ecutune.logparse.schema import CL_NORMAL       # noqa: E402

from . import arms, llm                             # noqa: E402
from .config import Config                          # noqa: E402

DRIVE_DIR = CAR / "logging" / "drive"
GROUND_TRUTH = "maf_low"
CONFOUND = "vacuum_leak"

# Open-ended arm: no enum to hide behind, so we can see whether the model reaches the SHAPE.
_OPEN_SYSTEM = (
    "You are diagnosing an engine-management problem from datalog evidence. Reason carefully "
    "from the numbers given. State what you think is wrong, how confident you are, and what "
    "single additional measurement would most cleanly confirm or refute it."
)


@dataclass
class Bundle:
    """Everything derived from the logs, with nothing interpretive attached."""
    n_rows: int
    n_steady_cl: int
    by_airflow: list[tuple[float, float, int, float, float]]   # maf, trim, n, load, rpm
    by_load: list[tuple[float, float, int, float]]             # load, trim, n, maf
    by_rpm: list[tuple[float, float, int, float]]              # rpm, trim, n, maf
    corr: dict[str, float]
    raw_rows: list[dict]


def _steady_closed_loop(ch: dict[str, np.ndarray]) -> np.ndarray:
    rpm, tps = ch["rpm"], ch["tps"]
    m = (rpm > 500) & np.isfinite(ch["maf_gs"]) & np.isfinite(ch["af_correction"])
    m &= np.abs(np.gradient(rpm)) <= 100.0
    m &= np.abs(np.gradient(tps)) <= 2.0
    if "fuel_system_status" in ch:
        m &= ch["fuel_system_status"] == CL_NORMAL
    return m


def build_bundle(files: list[Path], n_raw: int = 60, seed: int = 0) -> Bundle:
    chans: dict[str, list] = {}
    total = 0
    for f in files:
        lt = parse_romraider_csv(str(f))
        total += len(lt)
        for r in ("rpm", "tps", "maf_gs", "load", "af_correction", "af_learning",
                  "wideband_afr", "knock_retard", "coolant", "fuel_system_status"):
            chans.setdefault(r, []).append(lt.channels.get(r, np.full(len(lt), np.nan)))
    ch = {k: np.concatenate(v) for k, v in chans.items()}
    m = _steady_closed_loop(ch)
    trim = (ch["af_correction"] + ch["af_learning"])[m]
    maf, load, rpm = ch["maf_gs"][m], ch["load"][m], ch["rpm"][m]

    def _bin(x, edges, *companions):
        """(bin_lo, mean trim, n, *mean of each companion variable) for bins with >= 40 samples."""
        out = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            k = (x >= lo) & (x < hi)
            if k.sum() >= 40:
                out.append((float(lo), float(np.nanmean(trim[k])), int(k.sum()),
                            *(float(np.nanmean(c[k])) for c in companions)))
        return out

    # Each table reports the OTHER variables, so the model can see for itself that e.g. the
    # load bins and the rpm bins are confounded with airflow while airflow is not confounded
    # with them. Passing the wrong companion here would be a fabricated column in a blind
    # trial, which is why they are named explicitly rather than positional. (Bug caught
    # 2026-08-27: by_load/by_rpm were reporting mean LOAD in a column labelled airflow.)
    by_maf = _bin(maf, [0, 5, 10, 15, 20, 25, 30, 50], load, rpm)
    by_load_raw = _bin(load, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9], maf)
    by_rpm_raw = _bin(rpm, [500, 1000, 1500, 2000, 2500, 3000, 3600], maf)
    ok = np.isfinite(trim) & np.isfinite(maf) & np.isfinite(load) & np.isfinite(rpm)
    corr = {"airflow": float(np.corrcoef(trim[ok], maf[ok])[0, 1]),
            "load": float(np.corrcoef(trim[ok], load[ok])[0, 1]),
            "rpm": float(np.corrcoef(trim[ok], rpm[ok])[0, 1])}

    rng = np.random.default_rng(seed)
    idx = rng.choice(np.flatnonzero(m), size=min(n_raw, int(m.sum())), replace=False)
    idx.sort()
    raw = [{"rpm": round(float(ch["rpm"][i])), "maf_gs": round(float(ch["maf_gs"][i]), 2),
            "load_g_rev": round(float(ch["load"][i]), 3),
            "tps_pct": round(float(ch["tps"][i]), 1),
            "af_correction_pct": round(float(ch["af_correction"][i]), 2),
            "af_learning_pct": round(float(ch["af_learning"][i]), 2),
            "wideband_afr": round(float(ch["wideband_afr"][i]), 2),
            "coolant_f": round(float(ch["coolant"][i]))} for i in idx]
    return Bundle(total, int(m.sum()), by_maf, by_load_raw, by_rpm_raw, corr, raw)


def prompt_summary(b: Bundle, choices: list[str] | None) -> str:
    L = [
        "A 2.0 L turbocharged engine is running an ECU calibration written for a 2.5 L engine "
        "of the same family. It idles and drives. Below is pooled steady-state, CLOSED-LOOP "
        f"datalog evidence from {b.n_rows} logged rows ({b.n_steady_cl} steady closed-loop "
        "samples) across six drives, all in vacuum (no boost).",
        "",
        "'Total fuel trim' is short-term A/F correction plus long-term A/F learning, i.e. how "
        "much fuel the ECU is adding or removing on top of its base calculation to hold its "
        "commanded air/fuel ratio. Positive means it is adding fuel.",
        "",
        "TRIM vs MEASURED AIRFLOW",
        "  airflow g/s | total trim | n | mean load g/rev | mean rpm",
    ]
    for a, t, n, ld, rp in b.by_airflow:
        L.append(f"  {a:>6.0f}+      | {t:+7.1f}%   | {n:>5} | {ld:>10.2f}      | {rp:>6.0f}")
    L += ["", "TRIM vs ENGINE LOAD", "  load g/rev | total trim | n | mean airflow g/s"]
    for ld, t, n, mf in b.by_load:
        L.append(f"  {ld:>6.2f}+    | {t:+7.1f}%   | {n:>5} | {mf:>10.1f}")
    L += ["", "TRIM vs RPM", "  rpm | total trim | n | mean airflow g/s"]
    for rp, t, n, mf in b.by_rpm:
        L.append(f"  {rp:>5.0f}+ | {t:+7.1f}%   | {n:>5} | {mf:>10.1f}")
    L += ["",
          "CORRELATION of total trim with each variable:",
          f"  airflow {b.corr['airflow']:+.3f}   load {b.corr['load']:+.3f}   "
          f"rpm {b.corr['rpm']:+.3f}",
          "",
          "The wideband sensor confirms the ECU is HOLDING its commanded ratio throughout "
          "(measured within 0.1 AFR of command), so the trims above are the size of the "
          "correction required, not an uncorrected error.",
          ""]
    if choices:
        L.append("Which single fault best explains this evidence? Choose one of: "
                 + ", ".join(choices))
    else:
        L.append("What is wrong with this engine's calibration, and what is your reasoning?")
    return "\n".join(L)


def prompt_raw(b: Bundle, choices: list[str] | None) -> str:
    L = [
        "A 2.0 L turbocharged engine is running an ECU calibration written for a 2.5 L engine "
        "of the same family. It idles and drives. Below are randomly sampled steady-state, "
        f"CLOSED-LOOP rows from its datalogs ({b.n_steady_cl} such samples exist; "
        f"{len(b.raw_rows)} are shown). All in vacuum, no boost.",
        "",
        "Total fuel trim = af_correction_pct + af_learning_pct: how much fuel the ECU adds on "
        "top of its base calculation to hold its commanded ratio. Aggregate these rows however "
        "you find useful.",
        "",
    ]
    for r in b.raw_rows:
        L.append("  " + json.dumps(r))
    L.append("")
    if choices:
        L.append("Which single fault best explains this evidence? Choose one of: "
                 + ", ".join(choices))
    else:
        L.append("What is wrong with this engine's calibration, and what is your reasoning?")
    return "\n".join(L)


def run(out_path: Path, cfg: Config | None = None, seed: int = 0) -> list[dict]:
    cfg = cfg or Config()
    files = sorted(DRIVE_DIR.glob("drive-2026*.csv"))
    if not files:
        raise SystemExit(f"no drive logs under {DRIVE_DIR}")
    b = build_bundle(files, seed=seed)
    served = llm.health_check(cfg.llm)

    rows: list[dict] = []
    with open(out_path, "w", encoding="utf-8") as fh:
        for input_name, builder in (("summary", prompt_summary), ("raw", prompt_raw)):
            for arm_name, choices in (("forced_choice", list(FAULT_IDS)), ("open_ended", None)):
                user = builder(b, choices)
                schema = arms.answer_schema(choices) if choices else None
                system = arms.SYSTEM if choices else _OPEN_SYSTEM
                t0 = time.time()
                content, usage, latency = llm.chat(cfg.llm, system, user, json_schema=schema)
                answer = ""
                if choices and content:
                    try:
                        answer = json.loads(content).get("fault", "")
                    except json.JSONDecodeError:
                        answer = ""
                row = {
                    "suite": "e5_real_logs", "input": input_name, "arm": arm_name,
                    "model": served, "answer": answer, "content": content,
                    "correct": (answer == GROUND_TRUTH) if choices else None,
                    "chose_confound": (answer == CONFOUND) if choices else None,
                    "latency_s": round(latency, 1),
                    "finish_reason": usage.get("finish_reason"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "n_steady_cl": b.n_steady_cl, "seed": seed,
                    "wall_s": round(time.time() - t0, 1),
                }
                rows.append(row)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(f"  {input_name:8s} {arm_name:14s} -> "
                      f"{answer or '(open)':24s} {latency:6.1f}s "
                      f"finish={usage.get('finish_reason')}")
    return rows
