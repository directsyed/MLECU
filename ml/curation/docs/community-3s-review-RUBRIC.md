# Score-3 community doc review: FIXED RUBRIC (2026-08-16)

You are reviewing forum threads that an LLM judge scored 3/5 ("some substance, not enough to
promote") for MLECU, an AI-assisted ECU tuning system whose test car is a 2005 Subaru Forester
XT with a JDM EJ20X 2.0 L swap running the stock EJ255 2.5 L calibration, TGVs deleted, exhaust
AVCS deleted, VF48 turbo, catless. The car idles poorly and has never been driven.

The question is NOT "is this good writing" and NOT "is this correct" (a text reviewer cannot know
whether a fix actually worked). The question is: **would this thread be USEFUL if RETRIEVED for
the diagnostic queries the project currently lacks answers to?** Those gaps, in priority order:

1. Idle diagnosis: vacuum leak vs injector latency vs MAF scaling vs injector flow, what
   separates them in logs (trims vs airflow, trims vs battery voltage, smoke test results).
2. Smoke/leak testing procedure and what leaks look like in trims/AFR.
3. Healthy-idle MAF g/s baselines for EJ-series engines (esp. TGV-deleted), rpm dependence.
4. EJ20X-in-EJ255-calibration (or similar displacement/CR mismatch) symptoms and fixes.
5. VE / load-model correction from logged AFR vs target; timing for higher CR on 93 octane;
   knock handling. (Timing is a RETREAT mechanism in MLECU, removing timing autonomously,
   adding requires human review.)
6. RomRaider/ECUFlash/Openport logging + flashing procedure, SSM2, ROM read problems.
7. Wideband install/logging (AEM 30-0300), MegaSquirt/Speeduino content is LOW value unless it
   teaches a transferable diagnostic principle.

For EACH document, output ONE JSON object on ONE line (JSONL), no prose around it, with exactly:

{"id": <int>, "source": "<source>", "title": "<title, trimmed to 80 chars>",
 "summary": "<one line, <=25 words: what the thread actually contains>",
 "recommendation": "keep" | "drop",
 "reason": "<one line, <=30 words, judged on RETRIEVAL USEFULNESS for the gaps above>",
 "markers": {"outcome_reported": true|false, "causal_chain": true|false,
             "numbers_with_units_conditions": true|false, "thread_resolved": true|false,
             "corroboration": true|false},
 "topics": [<zero or more of: "vacuum_leak","smoke_test","idle","maf_scaling","maf_baseline",
            "injector_latency","injector_scaling","ve_tune","timing_knock","boost_control",
            "avcs","tgv","ej20x_swap","displacement_mismatch","wideband_afr","logging_method",
            "romraider_ecuflash_tooling","rom_read_flash","megasquirt_speeduino","generic_other">],
 "subaru_specific": true|false,
 "retrieval_value_for_current_gap": "high" | "medium" | "low"}

Rules:
- "keep" means: worth putting into the SEPARATE community retrieval index (tagged as a forum
  post) because a realistic diagnostic query would be well served by it. A post that says "same
  thing happened to me, smoke test found a torn intake boot, trims went from +12 to +2" is a
  KEEP even if it is two lines, because it is exactly what a vacuum-leak query needs.
- "drop" means: generic chat, unresolved speculation with no numbers, off-platform tooling talk
  with no transferable principle, parts-for-sale, or duplicated content.
- markers are about VERIFIABILITY SIGNALS, not correctness: did anyone report the outcome, is
  there a cause→effect chain, are there numbers WITH units and conditions, did the thread reach a
  resolution, does more than one poster corroborate.
- Read the whole document (Read tool; long files: read in offsets). The judge's rationale is at
  the top of each file; you may disagree with it.
- Do NOT invent content. If a doc is nearly empty, say so and drop it.
- Output ONLY the JSONL lines, one per doc, in id order. Nothing else.
