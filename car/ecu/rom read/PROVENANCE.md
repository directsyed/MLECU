# Stock ROM read — 2005 Forester XT (ECU 3B12504206 / cal A2WC411D)

**The original ROM. SACRED — never overwrite. Verify against `SHA256SUMS.txt` before trusting any copy.**

- File: `3B12504206_2026-08-16_16h51m01s.bin` — 1,048,576 bytes (1024 KB), full SH7058 flash.
- sha256: `11fe1536690e6b8f789d8719185a003c2d8ee73253ecd59a97a63f183a3f3118`
- md5:    `e88f016d3d32df251c9462fca1435ae9`
- Read: 2026-08-16 ~16:51 local, FastECU 0.1.0-beta.5 (patched, see `car/ecu/fastecu-patch/`),
  Washinglee Openport 2.0 clone via the logging shim, profile `sub_ecu_denso_sh7058`, K-line.

## How it was finally read (the blocker that was dead since project start)

The read had failed at `RequestDownload` (`7F 34 10 generalReject`) after a successful seed/key +
programming session. The `dataFormatIdentifier` sweep (0x00–0x04) made no difference — a clean
falsification: the ECU understood the request and refused it for a *permission* reason, not a
format one. Fix: **the Subaru green test-mode connectors (two single-pin greens under the driver
column) had to be joined** to enable read/write mode — a step our earlier notes wrongly dismissed
as "not applicable to a 2005 DBW car" (true for *logging*, false for *reading*). Lead came from
corpus doc 5793 (an 05 Forester that read only with "sti05 method + test connector"). With the
connectors joined, the plain upstream request went straight through — kernel uploaded to
0xFFFF3000, ROM read in ~2 minutes.

## Validity evidence (see the analysis in the 2026-08-16 handoff)

- **★ BYTE-IDENTICAL to an independent harvested known-stock reference.** This dump
  (`3B12504206_2026-08-16_16h51m01s.bin`, sha256 `11fe1536…3f3118`) equals
  `ml/data-pipeline/data/raw/roms/romraider/3B12504206_A2WC411D.bin` byte-for-byte (same sha256,
  1,048,576 B). This is the ROADMAP `--rom-diff`/"is it really stock" answer: an outside-source
  match proves the read is **complete** AND the ECU is **genuinely un-tuned** (a modified ROM would
  differ). Stronger than a self-consistency check.
- Cal ID `A2WC411D` + `Copr.DENSO2004` at 0x2000/0xC0000 — the expected USDM 2005 FXT AT calibration.
- Valid SH7058 reset vector at 0x0: PC=0x00000AAC, SP=0xFFFFBFA0.
- Entropy 4.65 b/byte, all 256 byte values present, real strings — genuine code+data, not a blank read.

## Copies (the original is archived in multiple places, per project rule)

1. `car/ecu/rom read/` (this dir, in git)
2. `data-backups/rom/` (in git)
3. **OFF-MACHINE (Syed): put it on a USB stick / cloud — a third, physical copy.** ← still to do

## Second read — now OPTIONAL (the byte-match already validates completeness)

The byte-identical match to the harvested reference (above) supersedes the need for a confirming
read — an independent *source* agreeing is stronger than a repeat of our own read. Still cheap
insurance if desired. Original note:

The connector works now, so re-read once more and `diff`/`sha256sum` against this file. Two
independent reads matching byte-for-byte is the gold standard for a sacred dump. Not blocking —
this dump is already validated internally — but cheap insurance.
