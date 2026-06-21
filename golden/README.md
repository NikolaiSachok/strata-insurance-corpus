# golden/

The **golden evaluation set**, generated *by construction* (the entity model is known, so answers are
knowable). See [BRIEF.md](../BRIEF.md) → "Golden evaluation set".

## `golden.jsonl` (committed)

The canonical committed eval, mirrored from the `sample/` slice by `make sample`. One JSON object per
line, aligned with general enterprise-RAG benchmark formats:

```json
{"id": "Q-C-1000-cause", "question": "What cause of loss was recorded for claim C-1000?",
 "answer": "hail damage", "relevant_doc_ids": ["DOC-C-1000-FNOL"],
 "query_class": "semantic", "provenance": {"entity_id": "C-1000", "field": "cause"}}
```

| Field | Meaning |
|---|---|
| `id` | Stable question id. |
| `question` / `answer` | The query and its ground-truth answer (a value recorded in the model). |
| `relevant_doc_ids` | Document(s) that support the answer (resolve via `manifest.json`). |
| `query_class` | `semantic` (M1) · `aggregation` / `multi_hop` (M4). |
| `provenance` | The `{entity_id, field}` the answer comes from. |

## Status

- ✅ **M1** — `semantic` / extractive class (one "cause of loss" question per FNOL).
- ⏳ **M4** — `aggregation` (computed from the model) + `multi_hop` (cross-doc / image fusion) classes;
  `eval.py` harness computing Recall@K / nDCG / answer-correctness (reuses Strata-RAG metrics where practical).
