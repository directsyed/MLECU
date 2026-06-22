# MLECU — HARDWARE STATE
**Authoritative current state as of June 19, 2026; driver/GPU bring-up verified June 22, 2026 (see §5).** This file supersedes all hardware details in older project docs (master-context.md, project-master-plan-v2.md, and all prior handoffs) where they conflict. This is the most frequently-changing context — keep it updated as the build evolves.

---

## 1. The server — Dell PowerEdge T630 (primary compute host)

- **Service tag:** GLRCBM2. **BIOS: 2.5.4** (ancient — MUST be updated before any CPU generation change; see §4).
- **Hostname:** `syedlab`. **Static IP `10.0.0.200`.** **iDRAC8 at `10.0.0.210`.**
- **OS:** Ubuntu Server 24.04, cloned from the Z800 via Clonezilla, running on a 1TB SATA SSD. Boot mode = **BIOS/legacy** (MBR + legacy GRUB — NOT UEFI).
- **CPU (current): ONE Intel Xeon E5-2630 v3** (8C/16T, 2.4GHz, AVX2 — modern ML frameworks run fine). **CPU2 socket empty; second heatsink missing.**
- **RAM:** 32GB ECC DDR4 (1866MHz, the CPU's max). **12 of 24 DIMM slots active** with one CPU (the rest wake with CPU2). Pipeline is RAM-starved — more RAM is wanted.
- **Chassis:** **16× 2.5" hot-swap backplane** (NOT 8×3.5" — older docs are wrong). 2× PSU bays. iDRAC8.
- **Storage controller:** **PERC H730 in slot 8** — supports HBA/passthrough. Plan: flip to **HBA mode for ZFS** (Configuration Management → Clear foreign config first → switch mode → reboot). Defer buying an LSI IT-mode card unless the H730 misbehaves.
- **NICs:** 2× Intel I350 GbE onboard + quad-port Broadcom BCM5719. Plenty.
- **Network:** `10.0.0.x` subnet, gateway `10.0.0.1`.

### T630 PCIe slot map (CRITICAL — verified against Dell docs)
- **Slots 1, 2, 3, 8 → CPU1 (ALIVE with one CPU).** Slots 1 & 3 = x16 Gen3; slot 2 = x8 Gen2 via PCH; slot 8 = internal PERC.
- **Slots 4, 5, 6, 7 → CPU2 (DEAD until a second CPU is installed).**
- Dell officially supports **one double-width 300W GPU on slot 3** in single-CPU config. A second GPU goes in **slot 6** — which requires CPU2.

## 2. GPUs (THREE cards in the picture)

### (a) HP OEM RTX 3090 — NEWLY ACQUIRED, INSTALLED IN T630, BOOTING
- Bought June 2026 inside a whole **HP Omen 45L PC for $1,100 cash**, local pickup. (Full acquisition/validation story below + in principles.md.)
- **GPU-Z confirmed:** NVIDIA GeForce RTX 3090, GA102, **24576 MB GDDR6X (Micron)**, 384-bit, 10496 shaders, Device ID 10DE 2204, BIOS 94.02.42.80.FE, **subvendor HP** (confirms OEM origin), stock reference clocks (1395/1695).
- **Provenance clean — NOT a mining card.** Bought new Jan 2026, ~2–3 weeks of use.
- **Fully validated:** OCCT VRAM (2 clean hrs), memtest_vulkan (clean past 4,325+ iterations), FurMark, GPU-Z all passed.
- **THERMAL FINDING: memory junction hit 106°C under memtest_vulkan** — this is a **thermal/pad-quality characteristic, NOT a defect** (zero errors at temp). Cause = OEM HP thermal pads + cramped Omen chassis. **REPAD DECISION DEFERRED until measured in the T630** (different thermal environment). Re-measure mem-junction in-server under load; repad (~$15–20 quality pads, mind the multi-thickness zone map) ONLY if still 105°C+ there.
- **Currently: installed in T630 slot 3** (it physically fits where the 3090 Ti did not — see below), powered via the interposer/DRXPD chain, **booting / ready to boot.** Driver not yet installed (see §5).

### (b) Zotac RTX 3090 Ti AMP Extreme Holo — VALIDATED, but UN-BENCHED in T630, BLOCKED
- Purchased earlier for $500. Has its 16-pin adapter (3× 8-pin → 16-pin) in hand, attached to the card.
- **Blocked on TWO fronts:**
  - **Power:** needs THREE 8-pin inputs (~450W). The Omen prebuilt can't power it (2×8-pin, ~800W, too tight). Its proper home is the T630 (1100W PSUs + cables).
  - **Physical clearance in T630:** **slot 3 is obstructed by the on-board "SW RAID" header** (the PERC software-RAID key standup). The Ti is too thick and contacts it. **Slot 1 also too thick. Slots 6/7 fit perfectly but are DEAD (no CPU2).** Syed could NOT remove the SW RAID obstruction (likely bare soldered pins).
  - **SAFETY: never force a card backplate against the SW RAID pins — short risk on power-up. Insulate or relocate.**
- **Path forward for the Ti:** install **CPU2 → slot 6 becomes live and fits the Ti**, OR use a **PCIe riser/extension cable** to float the Ti clear of the SW RAID header in slot 3.

### (c) The earlier validated 3090 (from prior sessions)
- Prior sessions reference a validated 3090. NOTE: the "$1,100 HP OEM 3090" in standing memory and the card acquired THIS session (§a) are **almost certainly the same card** — this session is its acquisition/validation/install story. If they turn out distinct, the GPU count and dual-GPU planning change — flag to Syed.

### Long-term GPU goal
4× RTX 3090 (~96GB pooled VRAM) for 70B+ QLoRA and 100B+ inference — gated behind addressing the T630 power ceiling (~1400W GPU draw vs PSU ceiling) and cooling. Far future.

## 3. GPU power delivery — the interposer chain (INSTALLED)

- **X7C1K Power Interposer Board — INSTALLED.** Syed has the interposer but NOT the full enablement kit (missing the **4999G plastic holder**; possibly the PDB feed cable).
- **CORRECTION (common forum error): the interposer's 40-pin connector is a BLACK PLASTIC HEADER, not a PCIe gold-finger edge connector.** It does NOT seat in a PCIe slot and does NOT mount on the rear of the motherboard. It receives a cable from the system PDB and mounts in the chassis power-distribution area. (A Dell forum post calling it "a female PCI plug" is WRONG/a different revision — disregard.)
- **Power chain:** PSU → PDB → 40-pin cable → X7C1K interposer → DRXPD cables → GPU power inputs.
- **DRXPD cables:** the official T630 GPU power cable (PCIe-pinout outputs, NOT the Tesla/EPS trap). Each DRXPD = one 6+2 (assembles to 8-pin) + one plain 6-pin. **2× ordered previously; 1 more in the current cart.** For the Ti's 3 inputs: 2× 8-pin from DRXPD + one **PCIe 6-pin→8-pin adapter (~$7)** to make the third. The 3090 (2×8-pin) needs less.
- **Multimeter ritual before first connection:** probe every 8-pin end for 12V/ground in PCIe positions — rules out clone/mislabel risk.

## 4. PSUs

- **Target/installed: 2× Dell 1100W (matching pair).** The old **2× 495W pair CANNOT run a 3090 Ti** — and critically, **redundant PSUs do NOT add** (either unit must carry the whole system alone, so 2× 495W = 495W capacity, not 990W).
- **1100W is the CORRECT target, not the budget choice:** Dell 1600W PSUs derate to ~800W on 120V household power; 1100W is the effective max on 120V. A 1100W pair also covers a future 2× power-capped-3090 config (~800–870W peak).
- **VERIFY:** confirm the PSUs currently in the T630 are the 1100W units, not the old 495W pair (since a GPU was just powered through the system).

## 5. Driver/boot state — DRIVER UP / GPU ENUMERATES (verified June 22, 2026)

**VERIFIED June 22, 2026 (`nvidia-smi` + `lspci`):** the OEM 3090 enumerates and the driver is up.
- `lspci`: `04:00.0 VGA … NVIDIA GA102 [GeForce RTX 3090]` (+ `04:00.1` HD audio).
- `nvidia-smi`: **RTX 3090, 24576 MiB, driver 580.159.03, CUDA 13.0**, idle **37 °C**, **75 W / 350 W** cap, 0 MiB used. The planned `nvidia-driver-580-server` install + reboot is **DONE**.
- `ipmitool` is **installed** on the host.

**Still open (next thread — run collaboratively as a teaching thread, see root CLAUDE.md learning mode):**
- **Fan curve / quieting.** 100% fans on an unrecognized PCIe card is expected T630 behavior; tame with `ipmitool raw` manual control: `0x30 0x30 0x01 0x00` → manual; `0x30 0x30 0x02 0xff 0x1e` ≈ 30%; revert `...0x01 0x01`. **CAUTION: manual mode disables auto-ramp — raise fan % before any GPU stress load or watch temps.** May need `sudo modprobe ipmi_devintf ipmi_si` first. Current fan %/mode not yet captured.
- **In-chassis mem-junction-UNDER-LOAD temp NOT yet measured** (card has only been observed idle at 37 °C). Run **gpu-burn + memtest_vulkan IN the T630** to get the real in-chassis memory-junction temp — **this is what settles the OEM-3090 repad decision (still DEFERRED).** Monitor: `nvidia-smi --query-gpu=temperature.gpu,temperature.memory,clocks.sm,power.draw,utilization.gpu --format=csv -l 2`.
- **Confirm the installed PSUs are the 1100W pair** (not the old 495W units) — a GPU has been powered through the system; verify physically/iDRAC when convenient.
- **Power-limit consideration:** older plan was `nvidia-smi -pl 300` for the Ti in-chassis (Dell 300W/slot spec). Revisit per-card once cards are stable.

## 6. Dual-CPU upgrade plan (REVISED this session)

Trigger has effectively fired (multiple GPUs exist; dual-GPU needs CPU2 to wake slots 6/7 — and slot 6 is also the Ti clearance fix).

- **REVISED PICK: 2× E5-2660 v4** (14C/28T each, **105W**) — same core count as the previously-planned 2680 v4 but 105W fits the **cheaper STANDARD heatsink** (120W is the heatsink-tier cutoff; the 2680 v4 needs the expensive high-performance heatsink). Trades only a little base clock (2.0 vs 2.4GHz), irrelevant for GPU-fed + always-on CPU work. Same 28C/56T total, lower heatsink cost.
  - ≤105W alternatives (standard heatsink): E5-2650 v4 (12C, 105W), E5-2640 v4 (10C, 90W).
- **Both CPUs must match** (model/stepping). **Need TWO heatsinks** (both can be standard now) + **thermal paste for both.**
- **BIOS-FIRST IS MANDATORY:** the v4 (Broadwell) chips need a BIOS newer than 2.5.4. **Update the BIOS while the known-good E5-2630 v3 is installed, THEN swap to the v4 pair.** v4 on old BIOS may = no-POST.
- **Verify CPU2-zone cooling fan(s)** present (T630 fan config matches CPU count).
- CPU2 also wakes the remaining 12 DIMM slots (helps RAM starvation).
- **Cart at session end (verify before checkout):** swap OUT the 2680 v4s → IN 2× E5-2660 v4; 2× standard heatsinks; thermal paste; 1× DRXPD cable; confirm CPU2 fan. **Update BIOS first.**

## 7. Other machines

- **HP Z800:** retired from server duty, brought home for the summer. Formerly at `10.0.0.200`. Pre-AVX E5620 CPUs → **NO GPU ever goes in it** (crashes PyTorch). Outstanding: power-button test, PS/2-keyboard BIOS fixes (After Power Loss=On, S5 WoL, ErP). Its 1TB WD Blue is the only copy of its data → first ZFS backup target via rsync once both machines are running.
- **Desktop (Ryzen 7 7700, SFF):** stays small/portable, untouched for compute.
- **Laptop (ThinkPad T14, Ryzen 7 Pro 4750U, 48GB):** primary remote client.

## 8. Storage roadmap

- 16× 2.5" bays suit **used enterprise SATA/SAS SSDs** (Intel S3610/S4510, Samsung PM863/883: ~$40–55/TB, high endurance, SMART-verifiable — demand wear screenshot before buying).
- **ZFS planned** (via H730 HBA mode). Start mirrored pair → grow to RAIDZ2.
- The **~7TB backup = personal photos/videos, slowly growing** → bulk-media tier; long-term lean is the Dell-documented 8×3.5" cage-swap (~$120–250 parts) for archive while SSD pool stays project-only. DEFERRED.

## 9. Remote access

- WireGuard VPN (`10.10.0.0/24` — must NOT overlap LAN `10.0.0.0/24`), Tailscale (Pi relay planned), DuckDNS (`syedslab.duckdns.org`).
- **WireGuard currently non-functional** (DuckDNS still points to old apartment IP, port-forward was on apartment router). Fall task — no urgency while LAN-local. At the house: WG comes in the clone; update DuckDNS to house IP; forward UDP 51820 on home router.
- Samba share at `/home/syed/Shared/`. Drive map `S:` → `\\10.0.0.200\SharedDrive`.

## 10. Endgame

Custom **4U EPYC watercooled build** (ROMED8-2T/H12SSL, EPYC 7402-class, external rad) when 3+ GPUs are truly needed AND the pilot-fine-tune-beats-RAG eval passes. The T630 is the interim bridge — GPUs and drives migrate out, T630 sells at ~purchase price (stable PowerEdge resale). Nothing stranded. Spend nothing on EPYC/watercooling at market price now.
