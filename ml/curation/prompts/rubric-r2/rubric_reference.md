# Scoring rubric: reference-tier documents (light judging)   [rubric-r2]

This document is from a TRUSTED source (FSM, engineering text, official tool docs, definition
files). You are NOT judging correctness; that was decided at the whitelist level and a
mid-size model does not overrule an FSM. You are scoring EXTRACTION USEFULNESS: is this
specific page/chunk usable fine-tuning material?

**5 - ** Dense, self-contained tuning knowledge: table semantics, calibration procedure,
diagnostic method, quantitative engineering relationships, understandable without the
surrounding book. A page you would hand a tuner as-is.

**4 - ** Solid reference content with minor context dependence (refers to absent figures or
adjacent sections, but the text carries its own meaning).

**3 - ** Real content, heavily context-dependent or fragmentary: parameter lists without
semantics, tables of values whose meaning lives on another page, mid-derivation fragments.

**2 - ** Page furniture: front-matter, tables of contents, legal text, navigation, references/
bibliography pages, near-empty extraction artifacts.

**1 - ** Extraction garbage: OCR noise, broken encoding, content-free fragments.

Rules:
- When torn, take the lower score.
- `relevance` and `evidence_in_images` fields apply here too (a figure-dependent page with
  its figures stripped: score the text, set evidence_in_images true).
- pairs: [] always, unless a genuine symptoms → diagnosis → change → outcome case study
  appears verbatim in the text (rare; some FSM diagnostic trees qualify).
- claims_checked: [] always; there is nothing to ground a trusted source against.
