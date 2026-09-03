# Reference grounding   [rubric-r2]

Below are snippets retrieved from the TRUSTED reference tier (definitions, FSMs, engineering
texts). Use them as the standard of correctness for this document's checkable claims:

- A claim SUPPORTED by a snippet strengthens the document's score within its anchor.
- A claim CONTRADICTED by a snippet on an engine-safety-relevant point (fueling direction,
  timing, knock response) forces score 1. Contradiction on a minor point caps the score at 2.
- Claims the snippets don't cover are "unverifiable", neither reward nor punish them.
- The snippets are retrieved by keyword match and may be IRRELEVANT to this document. An
  irrelevant snippet is not a contradiction, ignore it.

Record each checked claim in claims_checked with the snippet's REF id.
