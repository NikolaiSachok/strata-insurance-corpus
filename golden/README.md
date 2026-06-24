# golden/

The **golden evaluation set**, generated *by construction* (the entity model is known, so answers are
knowable). See [BRIEF.md](../BRIEF.md) → "Golden evaluation set".

## `golden.jsonl` (committed)

The canonical committed eval, mirrored from the `sample/` slice by `make sample`. One JSON object per
line, aligned with general enterprise-RAG benchmark formats:

```json
{"id": "Q-C-1000-cause", "question": "What cause of loss was recorded for claim C-1000?",
 "answer": "burglary", "relevant_doc_ids": ["DOC-C-1000-ADJ", "DOC-C-1000-FNOL"],
 "query_class": "semantic", "provenance": {"entity_id": "C-1000", "field": "cause"}}
```

| Field | Meaning |
|---|---|
| `id` | Stable question id. |
| `question` / `answer` | The query and its ground-truth answer. |
| `relevant_doc_ids` | **Every** document that asserts the answer (resolve via `manifest.json`). |
| `query_class` | `semantic` · `aggregation` · `multi_hop` (planned). |
| `provenance` | The `{entity_id, field}` the answer comes from. |

## Grounded by construction (#13)

Each question is built from the **provenance index** — the inversion of every document's recorded
`(entity, field, value)` assertions (see [`generator/provenance.py`](../generator/provenance.py)). So a
question's `answer` is *exactly* what its cited documents state, and `relevant_doc_ids` is *exactly* the
set of documents that assert it. `make validate` enforces this: every golden answer must equal the value
asserted by each of its cited documents, or validation fails.

## Status

- ✅ **`semantic`** — extractive facts: cause of loss, premium, settlement amount, insured vehicle,
  policyholder national identifier, lines of business.
- ✅ **`aggregation`** — corpus-level totals/counts (open reserve, total premium, open-claim count),
  asserted on the registers that tabulate them.
- ⏳ **`multi_hop`** (cross-doc / image fusion) class + an `eval.py` harness computing
  Recall@K / nDCG / answer-correctness (reuses Strata-RAG metrics where practical) — #14, #15.
