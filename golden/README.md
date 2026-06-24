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
| `query_class` | `semantic` · `aggregation` · `multi_hop`. |
| `provenance` | Single-hop: `{entity_id, field}`. Multi-hop: `{hops: [{entity_id, field, value, doc_ids}, …]}`. |

### Multi-hop (cross-document)

A `multi_hop` question's answer lives on a document you reach only by traversing from another, so its
provenance is the explicit **chain** and `relevant_doc_ids` spans the whole chain:

```json
{"id": "Q-MH-C-1003-vehicle", "question": "What make and model of vehicle was involved in claim C-1003?",
 "answer": "Opel Astra", "relevant_doc_ids": ["DOC-C-1003-FNOL", "DOC-MOT-0000005-DEC"],
 "query_class": "multi_hop",
 "provenance": {"hops": [{"entity_id": "C-1003", "field": "policy_id", "value": "MOT-0000005", "doc_ids": ["DOC-C-1003-FNOL"]},
                         {"entity_id": "MOT-0000005", "field": "vehicle", "value": "Opel Astra", "doc_ids": ["DOC-MOT-0000005-DEC"]}]}}
```

The FNOL ties the claim to its policy (the bridge); the declarations hold the policy's vehicle/premium. A
third pattern is a filtered lookup — identify a closed claim by its cause (FNOL/adjuster report) then read
its settlement amount (settlement letter). The answer is the terminal hop's value.

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
- ✅ **`multi_hop`** — cross-document joins (claim→policy→declarations for vehicle/premium; cause→settlement
  filtered lookup), each with an explicit, grounded hop chain.
- ⏳ An `eval.py` harness computing Recall@K / nDCG / answer-correctness (reuses Strata-RAG metrics where
  practical) — #15.
