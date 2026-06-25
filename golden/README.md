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
{"id": "Q-MH-C-1000-premium", "question": "What is the annual premium on the policy under which claim C-1000 was filed?",
 "answer": "€3,525.00", "relevant_doc_ids": ["DOC-C-1000-FNOL", "DOC-COM-0000003-DEC"],
 "query_class": "multi_hop",
 "provenance": {"hops": [{"entity_id": "C-1000", "field": "policy_id", "value": "COM-0000003", "doc_ids": ["DOC-C-1000-FNOL"]},
                         {"entity_id": "COM-0000003", "field": "annual_premium", "value": "€3,525.00", "doc_ids": ["DOC-COM-0000003-DEC"]}]}}
```

The FNOL ties the claim to its policy (the bridge); the policy's **annual premium** lives on the
declarations and appears on **no** claim document, so the join is genuinely required. The answer is the
terminal hop's value. Joins whose answer fact already co-occurs with the bridge on one document are
single-doc and are *not* emitted as multi-hop — e.g. a settlement letter stating both the cause and the
amount, or the FNOL, which already names the insured vehicle. (A test enforces that a multi-hop answer is
not readable in its bridge document.)

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
- ✅ **`multi_hop`** — cross-document joins (claim→policy→declarations for the policy's annual premium — a
  fact that lives on no claim document), each with an explicit, grounded hop chain.
- ✅ A reference **eval harness** ([`generator/eval.py`](../generator/eval.py)) computing
  Recall@K / nDCG@K / exact-match / token-F1.

## Eval harness

A small, dependency-free reference scorer so the corpus is usable **standalone with any RAG stack** (the
full engine is [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG); the M5 adapter mounts this corpus
into it). Feed it your system's predictions and it reports retrieval + answer metrics, broken down by query
class.

**Predictions file** — JSONL, one object per answered question (see
[`../sample/predictions.example.jsonl`](../sample/predictions.example.jsonl)):

```json
{"id": "Q-C-1000-cause", "retrieved_doc_ids": ["DOC-C-1000-FNOL", "DOC-C-1000-ADJ"], "answer": "burglary"}
```

`retrieved_doc_ids` is your ranked retrieval (best first); `answer` is your generated answer. A golden
question with **no** prediction scores 0 on every metric (coverage gaps count against the system).

| Metric | Meaning |
|---|---|
| `recall@K` | fraction of the relevant docs found in the top-K (so a 2-relevant-doc question caps `recall@1` at 0.5). |
| `ndcg@K` | rank-weighted retrieval quality (binary relevance). |
| `exact_match` | normalized exact answer match. |
| `token_f1` | token-overlap F1 (partial credit). |

```bash
make eval                                   # oracle self-check (perfect run -> 1.0)
make eval PRED=path/to/predictions.jsonl    # score your run against golden/golden.jsonl
python -m generator.eval --golden golden/golden.jsonl --predictions preds.jsonl --out metrics.json
```
