# sample/

A **small, committed slice** of the corpus so the repo is usable and inspectable without running a
full generation. Regenerated deterministically via `make sample` (seed 42, `sample` profile). The
**full** corpus is gitignored and published to HuggingFace — see [BRIEF.md](../BRIEF.md).

## Contents

Generated from 21 entities (6 policyholders, 3 agents, 2 adjusters, 5 policies, 5 claims) →
59 documents, 19 golden questions:

```
model.json                          canonical entity model (the spine)
roster.tsv                          id-keyed master-data index (the join target)
schema/                             JSON Schema for model.json + roster.tsv
docs/policy/*-declarations.pdf      declarations page (one per policy)
docs/policy/*-contract.docx         full policy contract — Word (one per policy)
docs/policy/*-endorsements.pdf      endorsement schedule (one per policy)
docs/policy/*-schedule.pdf          coverage schedule (one per policy)
docs/claim/*-fnol.pdf               First Notice of Loss form (one per claim)
docs/claim/*-adjuster-report.pdf    adjuster findings + disposition (one per claim)
docs/claim/*-estimate.pdf           damage/repair estimate (open & closed claims)
docs/claim/*-settlement-letter.pdf  settlement letter (closed claims)
docs/claim/*-denial-letter.pdf      denial letter (denied claims)
docs/claim/*-scanned.jpg            scanned (OCR-target) variants of FNOL + letters
docs/tabular/loss-run.xlsx          loss run — every claim (Excel)
docs/tabular/reserve-register.xlsx  open-claim reserves (Excel)
docs/tabular/premium-register.xlsx  policy premiums (Excel)
docs/tabular/commission-summary.csv per-agent commission (CSV)
docs/kb/underwriting-guidelines.md  underwriting guidelines (Markdown)
docs/kb/claims-handling-manual.docx claims handling manual (Word)
docs/kb/customer-faq.md             customer FAQ (Markdown)
evidence/*-evidence.jpg             AI damage/property photos — one per claim (rendered sample pixels)
image-prompts.jsonl                 seeded prompt-spec recipe for every evidence image (the reproducible artifact)
manifest.json                       every document + provenance + sha256
golden.jsonl                        golden eval questions (semantic + aggregation) — mirrored to ../golden/golden.jsonl
```

The `evidence/` images are AI-generated (non-deterministic pixels); `image-prompts.jsonl` is their committed,
reproducible recipe. The full corpus commits only the recipe — pixels are produced on-demand for the HF release.

Validate it: `make validate OUT=sample`.

More formats (knowledge base, scanned variants, images) are added to this slice as M2–M3 land.
See [docs/format-matrix.md](../docs/format-matrix.md) for the full plan.
