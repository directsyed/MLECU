# 2026-08-17 - HANDOFF: extended params installed; car session next (validation log + vacuum drive)

**Branches off `2026-08-17-overnight-morning-report.md`** (ML-side state: judge verdicts, C2 yield,
desk decisions; all still accurate, none re-stated here). This handoff covers the **car arc since
the ROM read** and is written to survive a context compaction: a fresh agent should be able to run
the next session from this file + `docs/OPEN-CHECKLIST.md` alone.

**Written 2026-08-17, after a compaction ate the fine session detail, extra-explicit on purpose.**

---

## 0. Where we are, one paragraph

The ROM is read (green test-mode connectors were the read/write permission gate; dump byte-identical
to a harvested stock reference ⇒ ECU genuinely un-tuned). The three-hold idle capture proved the warm
idle healthy and produced the first **measured MAF baseline**. The **log→layer bridge** exists: real
RomRaider CSVs now flow `parse → bin → Observation → identify() → clamped proposal` via
`ecutune.cli --diagnose`, and on the real holds the layer honestly refuses to distinguish
maf_high vs injector_flow (degenerate against a self-referential baseline, correct behavior).
The **57 extended parameters** for our absent-from-defs ECU (`3B12504206`) were recovered by sibling
reconciliation, cross-corroborated **byte-identical across two def versions a decade apart**
(2009 one-id-per-element + v370/2021 grouped-ids), spliced into Syed's real v370 logger def by a
surgical group-append (57 lines changed, every one only adds our id), and **Syed has installed the
patched def in RomRaider**. Nothing recovered is trusted yet, live validation is the very next act.

## 1. What changed this session (delta)

| commit | what |
|---|---|
| `30fcf8f` | three-hold capture committed + first validated MAF baseline (`MEASURED_MAF_BASELINE_20260816`) |
| `144473c` | records cleanup: ROM read SOLVED across all stale docs; workflow directive + role guardrail logged |
| `ebbf62d` | **the bridge**: `car/ecutune/logparse/observe.py` + `cli --diagnose` + 5 acceptance tests (car suite 101→106) |
| `dfbcb7f` | extended-param recovery: `car/ecu/defs/extended_param_recovery.py` + report + fragment + `EXTENDED-PARAMS-RECOVERY.md` |
| `97009d2` | MVEM re-ground (idle 700 rpm, measured airflow); `e4.py` status string honest |
| `9bc8e6a` | `car/logging/DRIVING-CAPTURE-PROTOCOL.md` (the vacuum coverage-sweep spec) |
| `f70cb34`, `24a75e4` | `patch_logger_def.py` + the **patched v370 def** (see §2) |
| (this handoff) | checklist refreshed (A2/A3/D/E were stale), this file |

Also: **E3 formally DEFERRED** (needs ≥1 closed propose→flash→re-log→outcome iteration for ground
truth; running it now would launder a sim number under the "real-car" label). Recorded in the plan
and decisions; do not re-litigate.

## 2. The extended-param def: exactly what was done (fine detail, post-compaction)

- Recovery: for each of 545 `ecuparam`s in the def, take the RAM address the **3B125 family agrees
  on** (AT revs 41/43, MT twin rev 42, MT 41/43; rev-40 pair `…04006/…84006` = known RAM outlier,
  excluded from the vote). 57 params recoverable, **all high confidence**, zero divergent.
- Cross-check: reconciliation run independently against the 2009 def and Syed's v370 def →
  **57/57 addresses identical**. Key channels: Feedback Knock `0xFF5C18`, CL Fueling Target
  `0xFF5610`, IAM `0xFF267C`, Target Boost `0xFF4BE4`, Injector PW `0xFF59AC`.
- Patch: v370 groups ids per address (`<ecu id="A,B,C">`); we **append `,3B12504206` to the
  existing group** that already carries the recovered address; no new XML nodes. Output:
  **`car/ecu/defs/romraider defs/logger_STD_EN_v370_3B12504206.xml`** (validated: XML parses,
  0 address/length mismatches, exactly 57 changed lines, ecuparam count unchanged).
- Two patcher bugs caught in validation BEFORE the file shipped (why `--create-nodes` is now
  default-OFF): `length="None"` emitted on 1-byte params (v370 omits length there), and
  duplicate-NAME ecuparams across protocol sections (e.g. `CL/OL Fueling*` = E3 *and* E33) getting
  a second, conflicting node.
- **Install state: DONE.** One stumble worth remembering: RomRaider's **Definition File Manager
  (Editor Definition Priority) rejects logger defs**, "not a valid Editor definition file". The
  logger def goes in the **logger** definition setting, a different slot. Syed resolved this
  himself; the patched def is loaded.
- **NOTHING IS VALIDATED YET.** Addresses are a strong prior (family agreement), not a measurement.
  The rev-40 outlier proves RAM layout *can* shift between revisions. A plausible-but-wrong RAM
  read is the worst failure mode for a layer that consumes these numbers.

## 3. NEXT SESSION: the exact sequence

### Act 1: Syed: the validation log (short, stationary + a short putter)
Channels: the new extended params (Feedback Knock, Fine Learning Knock, IAM, CL/OL Fueling,
CL Fueling Target, Target Boost, Boost Error, Injector #1 PW, Engine Load 4-byte, Knock Sum, Turbo
Dynamics) **plus `P21 Injector PW` and `P200 Engine Load`** (the standard twins, the comparison IS
the validation) **plus `P7 MAP`** and the usual idle set (rpm, MAF, AF corr/learn, battery V, ECT,
TPS, wideband). One continuous file, engine warm: ~30 s idle → a few neutral blips to ~2500 →
~1 min gentle vacuum driving. Green connectors **disconnected** for any driving.

### Act 2: Claude: validate each channel (the gate table, `EXTENDED-PARAMS-RECOVERY.md`)
IAM ≈ 1.00 · CL/OL flips to CL warm · extended Injector PW tracks P21 · Feedback Knock ≈ 0 (no
knock) · CL Fueling Target ≈ 14.7 at idle/cruise · Engine Load (4-byte) tracks P200 · Target
Boost/Error sane vs MAP. **Fail ⇒ DROP the channel, record it, do not rationalize.** Passing
channels become canonical roles in `car/ecutune/logparse/schema.py` so the layer can consume them.
IAM < 1.00 on a healthy warm engine = the ECU has already pulled timing, surface it to Syed
immediately, it changes the tuning conversation.

### Act 3: Syed: the vacuum driving log (`car/logging/DRIVING-CAPTURE-PROTOCOL.md`)
**HARD LINE: no boost.** P7 MAP stays below ~100 kPa, MAP is the boost gauge (no physical gauge on
the car). ~1500–3500 rpm, light-to-moderate load, hold each condition a few seconds, many distinct
(load, rpm) cells, 15–30 min, one file (`drive-vacuum-<date>.csv`). Watch the wideband: lean as load
rises or ANY knock retard ⇒ lift (that is the boost-leak/VE-lean tell, seen before it costs a
piston). DB9 pin-5-omitted ground-loop remedy; ECU params AND wideband updating together before
rolling. Validated extended channels in the profile if Act 2 passed; the capture is still worth
doing on the standard set if not.

### Act 4: Claude: the D19 build (the next LARGE objective)
From the driving log: **VE proposer** (per load/rpm cell, `VE_correction = measured_AFR /
target_AFR`; target from the validated `CL Fueling Target` channel, else read from the real ROM's
`fuel.target_afr_primary` via `read_semantic_tables`) and **timing retreat-only** (pull where
Feedback Knock shows knock; *adding* timing = human decision). New `algorithms/` stages in
`STAGE_REGISTRY`, behind the existing clamps (`ve_rate_limit ±3 %`, `knock_auto_abort`,
`timing_row_ceiling`). **The pipeline tunes; Claude builds and verifies; Syed approves**: Claude's
by-hand log reads are test oracles only, never the delivered diagnosis (role guardrail, decisions
2026-08-16).

### Act 5+: the path to the first flash (large objectives, in order)
1. **`romwrite`** (Phase E, safety-critical, nothing exists): inverse encoder (mirror of
   `reader._apply`), byte patcher on a ROM copy, SH7058 checksum recompute, semantic-scalar→cell
   map, behind `safety/`; byte-diff whitelist · read-back · checksum · bounds · human CHANGE
   REPORT; property-tested like the clamps.
2. **First FastECU WRITE**: its own milestone; write path is UNPROVEN (only read is). Preconditions:
   off-machine ROM copy (3rd location) + optional 2nd confirming read; green connectors ON for the
   flash; Syed's hand on the button.
3. Re-log → post-flash verify → **the first closed iteration** → archive as a training pair.
4. **E3 becomes runnable** (real ground truth exists at last): build `e3.py`, pre-register bars in
   DB meta BEFORE any arm runs (house rule), then run.
5. **Stage 0 smoke test before ANY boost tuning** (Syed's resequencing: after vacuum VE, before
   boost; the line is absolute). Then boost-region VE/timing.

## 4. Hanging items swept from the checklist (don't lose these)

- **Cold-idle Stage-2 gate**: Syed says one of the older committed logs
  (`car/logging/romraiderlog_20260811_213908.csv` or `…20260813_180435.csv`) is a genuine cold
  start (check the ECT ramp). **Nobody has verified this yet**: next agent: parse it, confirm
  cold-start + stable warm-up, close the gate item or ask for a fresh capture.
- **DTC read**: still open; deletes should set codes (their presence argues the ROM is unmodified).
- **DB9 shell rebuild**: dupont jumpers survived stationary holds; a driving capture shakes them.
  Before/with Act 3 if feasible.
- **Off-machine ROM copy**: still only 2 locations.
- **Desk decisions (Syed, parked, unchanged from the morning report):** 74 community keeps sign-off
  · E1 "dangerous" definition ruling · reindex/community-index calls · ≥4 promotion-gate rubric ·
  3.8-as-diagnosis-model · QLoRA retrain · push the unpushed commits (local is ~15 ahead).
- **FastECU upstream bug report**: Syed skipped; write-up ready if he changes his mind.

## 5. Standing context a fresh agent must carry

- **Roles (HARD, Syed 2026-08-16):** the PIPELINE tunes, Syed approves, Claude builds + verifies.
  Claude never hand-delivers tuning corrections from logs.
- **Safety architecture (HARD):** LLM proposes; deterministic hard-clamped human-reviewed code
  writes. Never design it away.
- **Workflow latitude (Syed 2026-08-16):** July guidelines are pre-data; optimize past them when
  the data warrants, log divergences in `decisions.md`.
- **Learning mode:** ML stack + fan curves = teach, Syed drives. Parsers/algorithms/scripting =
  build, then explain. Every CLI command explained flag-by-flag. Narrate actions live.
- **Test invocation:** `cd car && .venv/bin/python -m pytest tests/ -q` (106 green as of
  `24a75e4`); ml suites run from `car/.venv` too (ml/eval .venv lacks numpy).
- The car currently **drives and idles well** on the stock (2.5 L-calibrated) ROM; the tune is
  about correctness on the 2.0 L swap under load, not rescuing a limp.
