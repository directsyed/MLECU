# E2 probe file v2 — disposition table (2026-08-02)

Pre-authorized by Syed 2026-08-01; this table is the review artifact.
v1 is untouched on disk. Every disposition was decided against the SOURCE
TEXT in ref_fts, not against the audit's summary.

## Findings that CONTRADICT the audit

- **`e2-500-1` is not defective.** The audit read its expected value (32768) as absent from the evidence "with the expected sign", because the source writes `(x-32768)`. That was a PARSER bug, not a probe bug: an infix minus was being read as a sign. Fixed in Phase 1; probe kept unchanged.
- **`e2-5401-1` is not defective.** Its quote is verbatim in the source and its question matches: "outputs 0 volts in the presence of a magnetic field". Kept unchanged.
- **No probe qualifies as `derived`.** The audit proposed reclassifying 8-9 probes as derived and EXCLUDING them from the fabrication hard gate. Checked against source: **0 of 69** probes have an expected value that is absent from their source document. All 9 candidates state their value verbatim. Reclassifying them would have softened the gate on an unsupported premise, so they are kept gated and merely flagged (`derivable_wording`).
- **Quote fidelity is sound.** 18/69 quotes are not byte-identical to the source, but all 18 differ only by PDF artifacts (`injec - tion`, `particu late`, soft hyphens). Content is faithful in every case.

## Summary

- probes: 69
- keep: 59
- keep+flag (derivable wording, still gated): 9
- fix-question: 1
- drop: 0
- expected value absent from source: 0
- self-consistency failures (probe answered with its own expected value must score `exact`): 0

## Per-probe

| probe | disposition | expected | unit | selfcheck | value in source | quote verbatim | reason |
|---|---|---|---|---|---|---|---|
| e2-3927-1 | fix-question | `300` | bar | exact | yes | pdf-artifact | source states 300 bar as the ABSOLUTE main-injection NOP (pilot = 180 bar); v1 asked for the DIFFERENCE, so a model answering 120 correctly was convicted. Question rewritten to the absolute form; expected value unchanged. |
| e2-1398-0 | keep+flag | `107.5` | degrees | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-1398-1 | keep+flag | `105.5` | degrees | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-2008-2 | keep+flag | `5` | octane numbers | exact | yes | pdf-artifact | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-3694-0 | keep+flag | `9549` | dimensionless | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-3694-1 | keep+flag | `600` | dimensionless | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-3694-2 | keep+flag | `30 000` | dimensionless | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-5668-2 | keep+flag | `45 degrees` | degrees BTDC | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-5723-0 | keep+flag | `80` | psi | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-5723-1 | keep+flag | `11.8` | % | exact | yes | yes | question wording invites computation, but the value is stated verbatim in the source — remains a gated recall probe, broken out in the report. |
| e2-1076-0 | keep | `18 inches` | inches | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1165-0 | keep | `8` | ft-lbs | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-1165-1 | keep | `13` | hp | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-1165-2 | keep | `0.13` | seconds | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1309-0 | keep | `0.100` | inch | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1309-1 | keep | `12:1` | CR | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1919-0 | keep | `5 to 7° ATC` | ° ATC | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-1953-0 | keep | `3.5` | bar | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1953-1 | keep | `1500` | rev/min | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-1953-2 | keep | `1.0` | dimensionless (lambda) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2008-1 | keep | `30` | percent | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-2063-0 | keep | `23.9` | dimensionless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2063-1 | keep | `25.1` | dimensionless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2063-2 | keep | `22.4` | dimensionless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2097-0 | keep | `20°` | crank-angle BTC | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2097-1 | keep | `2 to 4` | (dimensionless) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2097-2 | keep | `2700` | K | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2207-0 | keep | `250` | °C | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-2241-0 | keep | `16` | dimensionless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2241-2 | keep | `2000` | rev/min | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2762-0 | keep | `100,000 to 130,000` | RPM | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2817-0 | keep | `18°` | bTDC | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2817-1 | keep | `12°` | aTDC | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-2817-2 | keep | `8°` | of engine rotation | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-2851-0 | keep | `60° to 40° bBDC` | Degrees bBDC | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-3461-0 | keep | `0.91 - 0.95` | dimensionless (efficiency ratio) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-3605-0 | keep | `7,000` | rpm | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-3804-0 | keep | `300 to 400 kPa (3 to 4 bar)` | kPa (bar) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-3838-0 | keep | `30 to 100 mJ` | mJ | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-3838-1 | keep | `1` | dimensionless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-3927-0 | keep | `180` | bar | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-4071-0 | keep | `0.5 to 4.5` | V | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-4071-1 | keep | `90` | °C | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-4448-0 | keep | `12` | V | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-4448-1 | keep | `3 to 30` | milliamperes | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-466-0 | keep | `.84` | unitless | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-4736-0 | keep | `450 mV` | mV | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-500-0 | keep | `0.01933677` | dimensionless (scaling factor) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-500-1 | keep | `32768` | raw data units | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5024-0 | keep | `1` | dimensionless (lambda ratio) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5113-0 | keep | `1` | dimensionless (lambda ratio) | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-5257-0 | keep | `450...500` | mV | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-5257-1 | keep | `800...1000` | mV | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5257-2 | keep | `about 350` | °C | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5291-0 | keep | `0.7` | Lambda | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-5291-1 | keep | `1` | Lambda | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-5401-0 | keep | `5 or 12` | volts | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5401-1 | keep | `0` | volts | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5490-0 | keep | `14.7:1` | ratio | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5490-1 | keep | `12.5:1` | ratio | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5490-2 | keep | `10 minutes` | minutes | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5579-0 | keep | `11.1:1` | air/fuel ratio | exact | yes | pdf-artifact | value stated in source; scorer v2 handles the form. |
| e2-5579-1 | keep | `140` | degrees Fahrenheit | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5579-2 | keep | `44` | degrees timing advance | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5668-0 | keep | `288 cc/min` | cc/min | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5668-1 | keep | `35 percent` | percent | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-5723-2 | keep | `15` | degrees | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-644-0 | keep | `20` | unitless (script constant) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
| e2-644-1 | keep | `0.9` | unitless (multiplier) | exact | yes | yes | value stated in source; scorer v2 handles the form. |
