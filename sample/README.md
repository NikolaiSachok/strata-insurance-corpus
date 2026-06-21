# sample/

A **small, committed slice** of the corpus so the repo is usable and inspectable without running a
full generation. Regenerated deterministically via `make sample` (seed 42, `sample` profile). The
**full** corpus is gitignored and published to HuggingFace — see [BRIEF.md](../BRIEF.md).

## Contents

Generated from 21 entities (6 policyholders, 3 agents, 2 adjusters, 5 policies, 5 claims) →
41 documents, 15 golden questions:

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
docs/tabular/loss-run.xlsx          loss run — every claim (Excel)
docs/tabular/reserve-register.xlsx  open-claim reserves (Excel)
docs/tabular/premium-register.xlsx  policy premiums (Excel)
docs/tabular/commission-summary.csv per-agent commission (CSV)
manifest.json                       every document + provenance + sha256
golden.jsonl                        golden eval questions (semantic + aggregation) — mirrored to ../golden/golden.jsonl
```

Validate it: `make validate OUT=sample`.

More formats (knowledge base, scanned variants, images) are added to this slice as M2–M3 land.
See [docs/format-matrix.md](../docs/format-matrix.md) for the full plan.
