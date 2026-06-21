# golden/

The **golden evaluation set**, generated *by construction* (the entity model is known, so answers are
knowable). See [BRIEF.md](../BRIEF.md) → "Golden evaluation set".

Planned:
- `golden.jsonl` — `{question, answer, relevant_doc_ids, query_class}` (semantic / aggregation / multi-hop),
  format aligned with general enterprise-RAG benchmarks for comparability.
- `eval.py` — harness computing Recall@K / nDCG / answer-correctness (reuses Strata-RAG metrics where practical).

Populated in M4. Empty until then.
