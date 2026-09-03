# MLECU: PRINCIPLES & HARD-WON LESSONS
Authoritative as of June 19, 2026. These are operational lessons learned through real experience on this project. They are FACTS/PRINCIPLES, not soft plan, don't contradict them, though you may extend them.

---

## 1. GPU verification protocol (for buying used cards)

The reliable signal that a used GPU is real and healthy, refined across multiple purchases:

- **Liveness proof beats clean screenshots.** A *photo of the monitor* showing GPU-Z with a live/dated browser visible is much harder to fake than a clean screenshot (which can be pulled off Google). Internal consistency matters too, e.g., GPU-Z subvendor "HP" matching a known HP OEM system corroborates origin.
- **GPU-Z first tab is the identity check:** confirms exact model + VRAM (24576 MB for a 3090) + GA102 die + device ID. A relabeled/fake card can't fake what GPU-Z reads off the silicon.
- **"Specs screenshot" is ambiguous**: always specify GPU-Z (first tab) or Task Manager → Performance → GPU. A generic Windows "System Information" spec list is useless for confirming the actual GPU.
- In-person test is the real gate before paying. Bring a USB stick with portable tools; run on the seller's rig (or yours) before cash changes hands. At short distances, conditional-on-inspection pickup is very doable.
- Public library = ideal neutral test site for a desktop (power + wifi + safety for both parties). Don't unplug library monitors, bring your own display + matching cable (3090 outputs DP/HDMI).
- A genuinely transparent, cooperative (even if non-technical) seller is a positive signal; a seller who keeps inventing reasons to avoid showing the GPU is a negative one. The library/public-meetup offer is itself a good test, a real seller takes it.

## 2. GPU stress-testing methodology

- **Tools to run (Windows):** GPU-Z (identity + sensors), OCCT (VRAM test + 3D Adaptive = core/render stress), FurMark (thermal), HWiNFO64 (logging). **Linux:** gpu-burn (FurMark-equiv), memtest_vulkan (VRAM, community standard for used cards), `nvidia-smi` query loop for logging.
- **OCCT test naming:** "**3D Adaptive**" = GPU core/render stress. Separate "**VRAM**" test = memory. "**Combined**" = total-board-power torture (use only as a short final capstone, and a reboot during Combined usually = PSU limit, NOT a bad card).
- CRITICAL false-error lesson (learned twice now): do NOT launch a sensor-polling tool (GPU-Z, HWiNFO) on top of an active OCCT/memtest VRAM run. Doing so while the test holds ~90% of VRAM produces false errors (one incident: ~168 false errors appeared the instant GPU-Z was opened mid-OCCT). The card was fine, clean hands-off re-run + memtest_vulkan confirmed it. Set HWiNFO logging BEFORE starting the stress test; then don't touch the machine.
- **Run validation tools in isolation**, not stacked; they compete for the card and contaminate each other's results.
- **VRAM faults are time/heat-soak dependent** → long soak (hours, overnight) is the right screen WHEN establishing health from zero. **Thermal/core faults surface fast** → ~45–60 min is plenty for 3D Adaptive. Once VRAM health is *established*, more VRAM-only hours add nothing, move to the untested thing (combined load, or a real workload).
- The best "long-term" test for this project = a real inference/QLoRA loop. Synthetic tests prove the silicon; a real sustained workload proves it'll do the actual job AND reveals sustained-load thermal throttling that a short burst won't.
- VRAM memory junction temp framework (GDDR6X on 3090): rated to **110°C** (hard throttle/protect ceiling). <90°C excellent; 90–100°C normal-warm; 100–104°C toasty (repad would help longevity); 105–110°C hot, near ceiling (repad candidate); 110°C+/throttling = repad needed. Zero errors at any temp <110°C = the memory is functional. Errors *with* high temp may be thermal (repad fixes) rather than dead silicon; errors at *reasonable* temp point to degraded silicon.

## 3. PSU / power safety (HARD RULES)

- NEVER run two PSUs to a single GPU simultaneously by improvising (e.g., a loose 8-pin from a bare second PSU). Ground-loop / rail-mismatch / unsynchronized 12V back-feeds across the card's PCB and kills the GPU/board. Legit dual-PSU needs an **ADD2PSU sync board** to tie grounds + trigger together. The improvised version is the unsafe version of a thing that's only safe when done deliberately.
- **Redundant PSUs do NOT add capacity**: either unit must carry the whole system alone (2× 495W = 495W usable, not 990W).
- Dell 1600W PSUs derate to ~800W on 120V household power. 1100W is the correct effective max on 120V.
- **All GPU power inputs must be populated** even when power-limited, sense pins set the card's power budget; a missing input = no-POST or hard-cap.
- Never force a card backplate against standup board pins (e.g., the T630 SW RAID header), short risk on power-up. Insulate or relocate.
- Multimeter every GPU power cable end before first connection: probe for 12V/ground in PCIe positions; rules out clone/mislabel.

## 4. Negotiation (for sourcing hardware)

- **Anchor first with a justified number** when the price is public and the market is known, whoever sets the reference point controls the haggling band. (This overrides the generic "never anchor first" advice, which applies when you DON'T know the other party's floor.)
- Compete on certainty + speed for distressed/motivated sellers, not purely price. A distressed seller's utility is cash-fast-certain, not last-dollar-maximization. A concrete cash + fast-pickup offer beats a marginally higher number ($25 more doesn't win a tie; readiness does).
- Never raise your offer without the other party naming a counter. "Can you up the offer?" / "I have another offer" with no number = a nudge to bid against yourself. Don't.
- Don't ask to strip the single most valuable part out of a bundle listing (e.g., the GPU out of a whole-PC listing), pivot to the whole unit; it reframes you from lowballer to serious buyer.
- Verify market pricing against eBay SOLD listings: stale comps invalidate negotiating arguments.
- "Financial distress" / "busy" framing is neutral-to-skeptical: never a reason to pay more or skip verification. It's also one of the most common softening scripts.

## 5. Market baselines (mid-2026, KEEP UPDATED)

- **Used RTX 3090: ~$900–1,050 average on eBay** (~$1,010 one tracker; range ~$820 low to ~$1,900 premium/NOS). The older $650–750 mental model is STALE/WRONG. Sub-$700 for a working 3090 = genuine deal territory, not baseline.
- A whole **HP Omen 45L (12900K + 3090)** bought for $1,100 was a strong deal, the 3090 alone is worth ~$1,000, the rest of the system effectively ~$200–350 on top. Part-out ceiling ~$1,375–1,710.
- **Scraper pricing thresholds** (external project) built on $600–800 assumptions are too low, set the "good deal" bar relative to ~$950–1,050. (Noted for awareness; the scraper is maintained separately.)
- i9-12900K used ~$200–260; 32GB DDR4-3200 ~$45–60; 1TB WD Black SSD ~$40–50; 6TB WD Black HDD ~$90–110.
- HP Omen 45L board is standard micro-ATX (NOT proprietary): card/board transplantable. (HP's *older* Omen lines DO use proprietary connectors, 45L-specific finding.)

## 6. T630 / server operational lessons

- **No PCIe bifurcation** (Dell firmware lock, not hardware), irrelevant for dual-GPU since each GPU gets its own physical x16 slot.
- **iDRAC fan behavior:** 100% fans on an unrecognized PCIe card is EXPECTED, not a fault. Tame with `ipmitool raw` (13th-gen PowerEdge commands).
- **PERC H730 → HBA mode:** clear foreign RAID config first (Configuration Management → Clear Configuration → reboot), then switch mode.
- **T630 boot mode = BIOS/legacy** (MBR + legacy GRUB, no UEFI).
- BIOS update must occur with the original/known-good CPU installed BEFORE any CPU generation change.
- **Netplan wildcard NIC matching** (`match: name: "en*"` + `optional: true`) is the robust pattern for OS clones moving to new hardware.
- Never boot two machines from the same clone simultaneously (identity/IP collision on 10.0.0.200).

## 7. ML / compute principles

- LLM mathematical reasoning is capable; deterministic algorithms are appropriate for safety-critical numerical outputs (e.g., ECU table writes), not because LLMs "can't do math" but because guaranteed precision/bounds matter for execution. (This is the foundation of the whole MLECU safety architecture.)
- **AVX2 is required for modern ML frameworks**: pre-AVX CPUs (Z800's E5620) crash PyTorch with "Illegal instruction." The E5-2600 v3/v4 Xeons have AVX2. AVX-512 (Xeon Scalable) matters for GROMACS/LAMMPS/NAMD but is nearly irrelevant for LLM inference once the GPU handles the load.
- ROCm 7.2 (March 2026) substantially improved AMD viability for inference, RX 7900 XTX and MI100 32GB are genuinely competitive now. AMD MI100 (CDNA1, gfx908, 32GB HBM2, 1228 GB/s) is under official ROCm support; MI50 (gfx906) deprecated 2024. Intel archived ipex-llm Jan 2026 → shifted to LLM Scaler/vLLM XPU path. (Context for any future accelerator decisions; the current path is Nvidia/CUDA.)

## 8. ECU flash discipline (when the car work reaches flashing)

- Stock ROM read + archived in multiple places BEFORE any write. The original ROM is sacred.
- Battery charger on the car; laptop on AC; verify the flash tool with hours of stable logging first.
- 32-bit Subaru ECUs (this car's) flash reliably and have recovery paths, discipline makes brick risk negligible.
- **Logging cable:** "VAG-COM KKL 409.1 USB" with GENUINE FTDI FT232RL chip. Reject CH340/PL2303 chips and ANY ELM327/OBDLink device (protocol interpreters can't speak raw SSM2). 2005 = SSM2-over-K-line (CAN diag came 2007+) → runs FreeSSM + RomRaider Logger. First connection reads ROM ID → confirms exact definitions.
- **Flash tool (32-bit ECU → 2.0-class hardware):** Openport 2.0 (genuine used, or a community-proven "Revision E" clone ~$50–80, NOT random $30 specials) supports ECUFlash/RomRaider; also does J2534 (covers logging). Openport 2.0 is out of production; genuine used runs $500+ (don't pay). Openport 3.0 reportedly in manufacturing (Jan 2026 Tactrix statement).
- **Keep the KKL cable regardless** ($20 = independent verification): confirm KKL and any clone read identical ROM ID + identical logs before trusting the clone to flash. Cable-vs-car fault isolation forever after.

## 9. Syed's working style (how to interact)

- **Communicates directly and technically.** Pushes back hard on hedging, deference, and narrow analysis. Wants to be told when an approach is wrong, with clear reasoning, not agreement by default. Do NOT just validate; problem-solve, and disagree when warranted (but not contrarily, only with good reason).
- Prefers dense, reasoning-forward answers. Wants the *why* (brief flag explanations for commands) over hand-holding. Flag entering new territory once, not repeatedly.
- **Requests comprehensive sweeps** when evaluating options (e.g., pushed for ~25-card GPU market analysis).
- **Strong pattern recognition**: catches scams, questions inconsistent technical claims, spots auction/proxy-bid mechanics. Treat him as a sharp peer.
- Prefers SSH-based workflow over physical console access wherever possible.
- **Prefers understanding what commands do** (brief flag explanations) over deep conceptual dives.
- Produces session handoffs for continuity; generates Claude Code planning-mode briefs and bootstrap architecture docs for complex work. (You now own this handoff function, see bootstrap brief §5.)
- LEARNING MODE (added 2026-06-22 interview; this is a learning project, not just a delivery). Split behavior by topic:
  - **Learning-priority**: the **LLM/ML stack** (curation, fine-tuning, LLM-judging, inference, eval) **and fan-curve / ipmitool calibration**: Syed wants to *learn* these. **Teach**: explain the *why*, go step-by-step, surface the commands/decisions and let him drive and absorb. **Do NOT auto-complete these for him.**
  - **Build-priority**: parsers, the deterministic tuning algorithms, general scripting ("your field to shine"): build them yourself, but always explain the design + mechanics afterward so he gains the knowledge. Never a black box.
  - **Never "just do everything."** Teach at peer density (no dumbing down). This refines, does not contradict, the "dense, anti-hand-holding" style above: stay dense and peer-level *while* teaching the learning-priority topics. Mirrored in the root `CLAUDE.md` behavioral contract.
