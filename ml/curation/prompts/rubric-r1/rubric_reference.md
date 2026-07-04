# Scoring rubric — reference-tier documents (light judging)   [rubric-r1, DRAFT for Syed review]

This document is from a TRUSTED source (FSM, definitions, engineering text, official docs).
You are NOT judging whether it is correct — that is presumed. You are scoring how USEFUL it is
as fine-tuning material for an ECU-diagnosis model.

**5 —** Dense, self-contained tuning knowledge: table semantics, calibration procedure,
diagnostic method, or quantitative engineering relationships, understandable without the
surrounding book/page.

**4 —** Solid technical reference content with minor context dependence (refers to figures or
sections not present, but the text carries its own meaning).

**3 —** Real content but fragmentary: parameter lists without semantics, tables of values whose
meaning lives elsewhere, heavy context dependence.

**2 —** Boilerplate, front-matter, legal text, page furniture, navigation, or near-empty
extraction artifacts.

**1 —** Extraction garbage: OCR noise, broken encoding, content-free fragments.

Rules: never extract pairs from reference docs unless a genuine symptoms → diagnosis → change →
outcome case study appears verbatim; claims_checked stays empty (there is nothing to ground a
trusted source against).
