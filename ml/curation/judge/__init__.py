"""MLECU Stage-B curation: the LLM-judge harness.

Scores corpus documents 1-5 against a versioned rubric (prompts/rubric-*/), grounding
community-tier docs in reference-tier retrieval, and extracts structured
(symptoms -> diagnosis -> change -> outcome) pairs. Writes through corpus_pipeline.State —
the pipeline owns the sqlite schema; this package is a client of it.
"""
