"""Seed the benchmark ledger with every unit of the three phases (2026-07-29).

Idempotent: labels are UNIQUE, so re-running adds only what's missing. Run with
  car/.venv/bin/python -m bench.seed [--phase burnin|guard|showdown|all]

PROTOCOL NOTES BAKED IN HERE (not incidental, comparability depends on them):
 * Arm B top-k is SUITE-SPECIFIC: E1v2 @3 (the incumbent's ratified 93.9% PASS cell),
   E2 @6 +guard (the B-v3 gate cell). A single k would make half the matrix
   non-comparable to the incumbent's records.
 * --probes and --cases are ALWAYS explicit: the CLI defaults are the 93-line draft probe
   file and the v1 case file, neither of which is what we measure.
 * --model-name always carries "<model>|<config-tag>" because the result FILENAME does not
   encode the model, only the row field does.
 * 1 run per challenger cell (Syed 2026-07-29); the incumbent's 4-invocation re-baseline
   establishes the noise band that decides what counts as a real difference.
"""
from __future__ import annotations

import argparse
import json

from . import ledger
from .driver import MLECU

E1V2 = "data/sim_cases_v2.jsonl"
PROBES = "data/e2_probes_v1.jsonl"
N_E1V2, N_E2 = 147, 69

BASE_GGUF = str(MLECU / "ml/curation/data/models/Qwen3.6-27B-Q8_0.gguf")
MOE35_GGUF = str(MLECU / "ml/curation/data/models/Qwen3.6-35B-A3B-Q8_0.gguf")
ADAPTER = str(MLECU / "ml/finetuning/runs/qlora-v1/adapter.gguf")
MODELS_DIR = MLECU / "ml/finetuning/models"


def prof(key, gguf, extra=None, ti_only=False) -> str:
    return json.dumps({"key": key, "gguf": gguf, "extra": extra or [], "ti_only": ti_only})


# ------------------------------------------------------------------ phase 1

def seed_burnin() -> None:
    """Serial. Nothing else may run until these pass, a bad DIMM would silently corrupt
    every downstream measurement, and B4 already proved this hardware isn't perfect."""
    units = [
        ("burnin-edac-baseline", "for f in /sys/devices/system/edac/mc/mc*/ce_count "
         "/sys/devices/system/edac/mc/mc*/ue_count; do echo \"$f=$(cat $f)\"; done "
         "| tee infrastructure/monitoring/edac-baseline-20260729.txt"),
        # memtester: 100G of the 165G free, one full pass of every pattern (walking ones,
        # checkerboard, bit spread/flip, XOR/SUB/MUL/DIV, sequential increment). ~6-9h.
        ("burnin-memtester-100g",
         "memtester 100G 1 > ml/finetuning/logs/memtester-20260729.log 2>&1"),
        # stress-ng: concurrent multi-threaded writers, the contention pattern memtester's
        # single-threaded walk cannot produce. 28 workers = one per physical core.
        ("burnin-stressng-vm",
         "stress-ng --vm 28 --vm-bytes 4G --vm-method all --verify --timeout 2h "
         "--metrics-brief > ml/finetuning/logs/stressng-20260729.log 2>&1"),
        # Real aggregate bandwidth across both NUMA nodes, replaces my ~120GB/s estimate
        # with a measurement, and is the number the MoE offload projections rest on.
        ("burnin-numa-bandwidth",
         "numactl --interleave=all stress-ng --stream 28 --stream-madvise hugepage "
         "--timeout 120 --metrics-brief > ml/finetuning/logs/numa-bw-20260729.log 2>&1"),
        ("burnin-edac-final", "for f in /sys/devices/system/edac/mc/mc*/ce_count "
         "/sys/devices/system/edac/mc/mc*/ue_count; do echo \"$f=$(cat $f)\"; done "
         "| tee infrastructure/monitoring/edac-final-20260729.txt"),
    ]
    for i, (label, cmd) in enumerate(units):
        ledger.add_unit(phase="burnin", seq=i, label=label, kind="shell",
                        argv_json=json.dumps([cmd]))


# ------------------------------------------------------------------ phase 2

def seed_guard() -> None:
    """Noise band + MTP causality + the guard cells we never ran."""
    base_mtp = prof("base-mtp", BASE_GGUF, ["--spec-type", "draft-mtp"])
    base_nomtp = prof("base-nomtp", BASE_GGUF)
    ft_mtp = prof("ft-nomtp", BASE_GGUF, ["--lora", ADAPTER])   # lora+MTP untested; omit MTP
    seq = 0

    # (1) The noise band / MTP experiment: SAME cell, 4 separate invocations.
    # 2 with MTP + 2 without answers three questions at once, how much variance a
    # comparison must clear, whether MTP causes the cross-invocation drift, and what the
    # 93.9% cell scores on CURRENT retrieval code (it predates the 07-25 retriever fixes).
    for i in (1, 2):
        for tag, profile in (("mtp", base_mtp), ("nomtp", base_nomtp)):
            name = f"qwen27b-dense|noise-{tag}-{i}"
            ledger.add_unit(
                phase="guard", seq=seq, model_key="qwen27b-dense",
                label=f"guard-noise-{tag}-{i}", kind="harness", server_profile=profile,
                arm="B", suite="e1v2", model_tag=name, n_rows_expected=N_E1V2,
                argv_json=json.dumps(["--run-e1", "--arm", "B", "--runs", "1",
                                      "--cases", E1V2, "--top-k", "3",
                                      "--retrieval-mode", "hybrid", "--model-name", name]))
            seq += 1

    # (2) Arm D + guard, the guard's live value has never been measured on a model that
    # actually fabricates (base attempted 1; the fine-tune attempted 14-15).
    name = "qwen27b-q8+qlora-v1|hybrid-k6+guard"
    ledger.add_unit(phase="guard", seq=seq, model_key="qwen27b-ft", label="guard-armD-k6",
                    kind="harness", server_profile=ft_mtp, arm="D", suite="e2",
                    model_tag=name, n_rows_expected=N_E2,
                    argv_json=json.dumps(["--run-e2", "--arm", "D", "--runs", "1", "--guard",
                                          "--probes", PROBES, "--top-k", "6",
                                          "--retrieval-mode", "hybrid", "--model-name", name]))
    seq += 1

    # (3) Arm B + guard at k3, completes the guard matrix.
    name = "qwen3.6-27b-q8_0|hybrid-k3+guard"
    ledger.add_unit(phase="guard", seq=seq, model_key="qwen27b-dense", label="guard-armB-k3",
                    kind="harness", server_profile=base_mtp, arm="B", suite="e2",
                    model_tag=name, n_rows_expected=N_E2,
                    argv_json=json.dumps(["--run-e2", "--arm", "B", "--runs", "1", "--guard",
                                          "--probes", PROBES, "--top-k", "3",
                                          "--retrieval-mode", "hybrid", "--model-name", name]))
    seq += 1

    # (4) Judge batch fills the gap (314 docs pending incl. re-queued 5781). Own venv.
    ledger.add_unit(phase="guard", seq=seq, model_key="", label="guard-judge-batch",
                    kind="shell",
                    argv_json=json.dumps([
                        "cd ml/curation && .venv/bin/python -m judge.cli --run "
                        "> data/judge-run-bench-20260729.log 2>&1"]))


# ------------------------------------------------------------------ phase 3

# Paths + quants VERIFIED against the HF API 2026-07-29 (sizes are the real blob totals).
# llama.cpp loads a sharded GGUF by pointing -m at shard 00001; siblings are auto-detected.
# `-ncmoe N` = keep the MoE (expert) weights of the first N layers on CPU. Starting values
# are conservative estimates; the driver's duty watchdog and an OOM retry adjust upward.
SHOWDOWN = [
    # key, gguf path, extra server flags
    ("qwen35-moe", MOE35_GGUF, ["-ncmoe", "12"]),                       # 35.2 GB Q8, on disk
    ("qwen-next-80b", str(MODELS_DIR / "qwen-next-80b/Q6_K/"
                          "Qwen3-Next-80B-A3B-Instruct-Q6_K-00001-of-00002.gguf"),
     ["-ncmoe", "28"]),                                                 # 65.5 GB Q6_K
    ("gpt-oss-120b", str(MODELS_DIR / "gpt-oss-120b/gpt-oss-120b-MXFP4.gguf"),
     ["-ncmoe", "20"]),                                                 # 63.4 GB NATIVE MXFP4
    # DEVIATION FROM THE Q6 FLOOR, deliberate and logged: Mistral's UD-Q6_K is 99.4 GB,
    # which forces ~77 GB into RAM and lands the cell below the >=10 t/s interactive floor
    #, i.e. Q6 would make this cell unmeasurable rather than merely slow. MXFP4_MOE
    # (71.8 GB) is the MoE-optimised 4-bit format, directly analogous to gpt-oss's native
    # release, keeping the two 100B-class cells comparable. Mistral is the droppable
    # exploratory cell; flagged for Syed in the final report.
    ("mistral-small-4", str(MODELS_DIR / "mistral-small-4/MXFP4_MOE/"
                            "Mistral-Small-4-119B-2603-MXFP4_MOE-00001-of-00003.gguf"),
     ["-ncmoe", "32"]),                                                 # 71.8 GB MXFP4_MOE
]


def seed_showdown() -> None:
    """4 cells per model: E1v2 arm A + arm B@3, E2 arm A + arm B@6+guard. 1 run each."""
    seq = 0
    for model_key, gguf, extra in SHOWDOWN:
        p = prof(model_key, gguf, extra)
        cells = [
            ("e1v2", "A", None, ["--run-e1", "--arm", "A", "--runs", "1", "--cases", E1V2],
             N_E1V2, "e1v2-armA"),
            ("e1v2", "B", 3, ["--run-e1", "--arm", "B", "--runs", "1", "--cases", E1V2,
                              "--top-k", "3", "--retrieval-mode", "hybrid"], N_E1V2, "e1v2-armB-k3"),
            ("e2", "A", None, ["--run-e2", "--arm", "A", "--runs", "1", "--probes", PROBES],
             N_E2, "e2-armA"),
            ("e2", "B", 6, ["--run-e2", "--arm", "B", "--runs", "1", "--guard",
                            "--probes", PROBES, "--top-k", "6",
                            "--retrieval-mode", "hybrid"], N_E2, "e2-armB-k6-guard"),
        ]
        for suite, arm, _k, argv, nrows, tag in cells:
            name = f"{model_key}|{tag}"
            ledger.add_unit(phase="showdown", seq=seq, model_key=model_key,
                            label=f"show-{model_key}-{tag}", kind="harness",
                            server_profile=p, arm=arm, suite=suite, model_tag=name,
                            n_rows_expected=nrows,
                            argv_json=json.dumps(argv + ["--model-name", name]))
            seq += 1


# ------------------------------------------------------------------ phase 4 (2026-08-02)

PROBES_V2 = "data/e2_probes_v2.jsonl"

# The CALIBRATED profiles the showdown actually adopted, read back out of the ledger and
# cleaned up (the calibrator appended its -ot flags twice on two models: harmless but
# confusing, and llama.cpp takes the last one anyway). Every profile carries ctx 24576:
# prompt and completion share the window, so a 16384 completion budget cannot live in a
# 16384 context. That was the 2026-08-01 truncation defect and it is not repeatable here.
FT_MODELS = MLECU / "ml/finetuning/models"
_HI = ["--chat-template-kwargs", '{"reasoning_effort":"high"}']
_OT = lambda lo, hi, dev: ["-ot", r"blk\.(" + "|".join(str(i) for i in range(lo, hi + 1))
                           + r")\.ffn_.*_exps\.weight=" + dev]

E2V2_MODELS = [
    # (model_key, profile dict, include_e1v2_armB_reverify)
    ("qwen27b-dense", {"key": "base-nomtp-ctx24k", "gguf": BASE_GGUF, "extra": [],
                       "ti_only": False, "ctx": 24576}, True),
    ("gpt-oss-120b", {"key": "gpt-oss-120b-ot13-ctx24k",
                      "gguf": str(FT_MODELS / "gpt-oss-120b/gpt-oss-120b-MXFP4.gguf"),
                      "extra": _OT(0, 12, "CUDA1") + _OT(24, 35, "CPU") + _HI,
                      "ti_only": False, "tensor_split": "1,0", "ctx": 24576}, True),
    ("qwen35-moe", {"key": "qwen35-moe-ot18-ctx24k", "gguf": MOE35_GGUF,
                    "extra": _OT(0, 17, "CUDA1"),
                    "ti_only": False, "tensor_split": "1,0", "ctx": 24576}, False),
    ("qwen-next-80b-think",
     {"key": "qwen-next-80b-think-ot17-ctx24k",
      "gguf": str(FT_MODELS / "qwen-next-80b-thinking/Q6_K/"
                  "Qwen3-Next-80B-A3B-Thinking-Q6_K-00001-of-00002.gguf"),
      "extra": _OT(0, 16, "CUDA1") + _OT(32, 47, "CPU"),
      "ti_only": False, "tensor_split": "1,0", "ctx": 24576}, False),
    ("mistral-small-4",
     {"key": "mistral-small-4-ot11-ctx24k",
      "gguf": str(FT_MODELS / "mistral-small-4/MXFP4_MOE/"
                  "Mistral-Small-4-119B-2603-MXFP4_MOE-00001-of-00003.gguf"),
      "extra": _OT(0, 10, "CUDA1") + _OT(21, 35, "CPU") + _HI,
      "ti_only": False, "tensor_split": "1,0", "ctx": 24576}, False),
]

# Uniform across every cell: these are the comparability contract, not tuning knobs.
E2V2_COMMON = ["--max-tokens", "16384", "--timeout", "1800", "--retrieval-mode", "hybrid"]


def seed_e2v2() -> None:
    """The bench-integrity rerun: E2 re-derived on fixed instrumentation + probes v2.

    MTP is OFF everywhere. MTP is NOT output-invariant (measured 2026-07-31: 91.2% answer
    agreement on-vs-off), so it is a variable, and a comparison matrix may hold only one
    value of a variable. The deployed 27B still serves MTP-on; that is a serving decision,
    not a measurement one.

    DELIBERATE EXPANSION of the plan's 10 cells to 15, logged in decisions.md: the plan
    reruns arm B only, on the reasoning that the snippet fix cannot touch a closed-book arm.
    True, but `finish_reason` did not exist when the arm-A cells were run, so their empty
    completions cannot be separated into truncated vs no_answer retroactively, and arm A is
    where most empty completions happened. The A2 fix is unmeasurable on arm A without a
    rerun. ~4h added to a ~17h run to close a gap the plan itself opens.

    Ordering is by model (one server load each, and loads cost 5-20 min) with the two
    FINALISTS first, so the cells that decide deployment land in the first ~12 hours.
    """
    seq = 0
    for model_key, profile, reverify in E2V2_MODELS:
        p = json.dumps(profile)
        cells = [
            ("e2", "A", ["--run-e2", "--arm", "A", "--runs", "1",
                         "--probes", PROBES_V2], N_E2, "e2v2-armA"),
            ("e2", "B", ["--run-e2", "--arm", "B", "--runs", "1", "--guard",
                         "--probes", PROBES_V2, "--top-k", "3"], N_E2, "e2v2-armB-k3-guard"),
            ("e2", "B", ["--run-e2", "--arm", "B", "--runs", "1", "--guard",
                         "--probes", PROBES_V2, "--top-k", "6"], N_E2, "e2v2-armB-k6-guard"),
        ]
        if reverify:
            # Syed ratified 2026-08-01: finalists only. The arm-B E1 prompts also consumed
            # truncated snippets, and "the enum answers make it plausibly small" is not a
            # measurement.
            cells.append(("e1v2", "B", ["--run-e1", "--arm", "B", "--runs", "1",
                                        "--cases", E1V2, "--top-k", "3"],
                          N_E1V2, "e1v2-armB-k3-reverify"))
        for suite, arm, argv, nrows, tag in cells:
            name = f"{model_key}|{tag}"
            ledger.add_unit(phase="e2v2", seq=seq, model_key=model_key,
                            label=f"e2v2-{model_key}-{tag}", kind="harness",
                            server_profile=p, arm=arm, suite=suite, model_tag=name,
                            n_rows_expected=nrows,
                            argv_json=json.dumps(argv + E2V2_COMMON
                                                 + ["--model-name", name]))
            seq += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all",
                    choices=("burnin", "guard", "showdown", "e2v2", "all"))
    args = ap.parse_args()
    ledger.init()
    if args.phase in ("burnin", "all"):
        seed_burnin()
    if args.phase in ("guard", "all"):
        seed_guard()
    if args.phase in ("showdown", "all"):
        seed_showdown()
    if args.phase == "e2v2":            # NOT part of "all": the showdown phases are history
        seed_e2v2()
    print(json.dumps(ledger.status(), indent=2))


if __name__ == "__main__":
    main()
