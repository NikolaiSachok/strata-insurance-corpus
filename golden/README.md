# golden/

The **golden evaluation set**, generated *by construction* (the entity model is known, so answers are
knowable). See [BRIEF.md](../BRIEF.md) → "Golden evaluation set".

## `golden.jsonl` (committed)

The canonical committed eval, mirrored from the `sample/` slice by `make sample`. One JSON object per
line, aligned with general enterprise-RAG benchmark formats:

```json
{"id": "Q-KB-lines", "question": "Which lines of business does Meridian Mutual underwrite?",
 "answer": "Motor, Household, Commercial", "relevant_doc_ids": ["DOC-KB-UW"],
 "query_class": "semantic", "modality": "text", "provenance": {"entity_id": "CORPUS", "field": "lines_of_business"}}
```

| Field | Meaning |
|---|---|
| `id` | Stable question id. |
| `question` / `answer` | The query and its ground-truth answer. |
| `relevant_doc_ids` | **Every** document that asserts the answer (resolve via `manifest.json`). |
| `query_class` | `semantic` · `aggregation` · `multi_hop` (the reasoning shape). |
| `modality` | The input a system must read to answer: `text` · `ocr` · `vision` · `multimodal_retrieval` · `cross_modal`. |
| `provenance` | Single-hop: `{entity_id, field}`. Multi-hop: `{hops: [{entity_id, field, value, doc_ids}, …]}`. |

### Multimodal (OCR / vision / retrieval / cross-modal)

`query_class` describes the reasoning shape; `modality` describes the **input a system must read**. Beyond
`text`, four modalities have answers that live only in a scanned or image document, so answering genuinely
requires the modality — the seeded image **prompt-spec** (or the rendered scan) is the by-construction label:

| `modality` | Answer lives in | Example |
|---|---|---|
| `ocr` | a **scan-only** police report (no born-digital twin) | *"police report reference number for claim C-1000?"* |
| `vision` | an evidence photo's visible content | *"which part is visibly damaged in the photo for C-1000?"* |
| `multimodal_retrieval` | an on-file ID portrait (retrieve the image) | *"retrieve the ID portrait of policyholder PH-00006"* |
| `cross_modal` | a text→image chain | *"what is damaged in the photo for the claim under policy P?"* |

A **leak-guard** test asserts every `ocr` / `vision` / `cross_modal` answer appears on **no** born-digital
page — otherwise the question would be answerable by text retrieval alone (the same discipline as the
multi-hop bridge guard). `multimodal_retrieval` answers are descriptive captions and are exempt.

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
- ✅ **multimodal** (`modality`: `ocr` · `vision` · `multimodal_retrieval` · `cross_modal`) — answers that
  live only in a scanned or image document, grounded on scan-only / image-only ground truth, with a
  leak-guard test.
- ✅ A reference **eval harness** ([`generator/eval.py`](../generator/eval.py)) computing
  Recall@K / nDCG@K / exact-match / token-F1.

## Eval harness

A small, dependency-free reference scorer so the corpus is usable **standalone with any RAG stack** — it
scores *predictions* against the labels so every consumer scores identically; it does not do retrieval, and
this repo ships no engine adapter (ingestion is the consuming system's job — see
[docs/data-card.md](../docs/data-card.md)). Feed it your system's predictions and it reports retrieval +
answer metrics, broken down by query class **and by modality** (so OCR / vision / retrieval capability is
scored on its own).

**Predictions file** — JSONL, one object per answered question (see
[`../sample/predictions.example.jsonl`](../sample/predictions.example.jsonl)):

```json
{"id": "Q-KB-lines", "retrieved_doc_ids": ["DOC-KB-UW", "DOC-KB-FAQ"], "answer": "Motor, Household, Commercial"}
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
