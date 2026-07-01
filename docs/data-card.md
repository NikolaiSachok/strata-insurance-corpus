# Data card & ingestion contract

**This repository is a data vendor.** It ships a reproducible, synthetic, multi-format insurance
document corpus plus its **ground truth** — and nothing about *how* to process it. Ingestion,
OCR, chunking, embedding, retrieval, and vision are the **consuming RAG system's** responsibility.
The corpus does not carry, prescribe, or depend on any engine's adapter, parser, or plugin API.
(It composes cleanly with [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG) — that engine's
own agent writes the adapter on its side — but it is engine-agnostic by construction.)

This document is the contract a consumer codes against: what files exist, what each means, how the
ground truth is structured, and how to score against it.

## What you get

Run `make generate SEED=42` (full corpus, gitignored) or use the committed `sample/` slice. Either
way the output root contains:

| Path / file | What it is | Consumer action |
|---|---|---|
| `docs/policy/…`, `docs/claim/…`, `docs/tabular/…`, `docs/kb/…`, `docs/identity/…` | The documents — PDF (born-digital), `.docx`, `.xlsx`, `.csv`, `.md`, and scanned `.jpg` variants | parse / OCR to text yourself |
| `evidence/…`, `faces/…` | AI evidence photos + ID portraits (pixels; committed for `sample/`, on-demand for the full set) | vision / caption / image-embed yourself |
| `manifest.json` | Every document with `doc_id`, `doc_type`, `format`, `path`, `sha256`, `entity_ids`, and its `provenance` (the `(entity, field, value)` facts it asserts) | resolve a `doc_id` → file + the facts it states |
| `golden.jsonl` | The golden evaluation set (see below) | the questions/answers you retrieve + answer against |
| `pii-index.jsonl` | Redaction ground truth: every PII span (`doc_id`, `pii_type`, `field`, `value`, `modality`) | score your PII/redaction layer against it |
| `image-prompts.jsonl` | The seeded prompt-spec that *generates* each image — and doubles as its by-construction **label** | reproduce pixels / use as vision ground truth |
| `model.json`, `roster.tsv`, `schema/` | The entity model, the master-data roster (join target for "who/what owns this"), and JSON Schemas | master-data joins, validation |

## You own ingestion — the corpus doesn't dictate it

The corpus deliberately ships documents in their native, real-world forms and **does not** pre-extract
a clean-text layer. That is a design choice, not an omission:

- **PDF / docx / xlsx / csv / md** — extract text with your own stack (pdfplumber/pypdf, python-docx,
  openpyxl, etc.). The born-digital documents carry a real text layer.
- **Scanned `.jpg` variants** — these are *images of documents*. You must **OCR** them. There is no
  clean-text sidecar: shipping one would hand you the answer and defeat the OCR test.
- **Evidence photos / ID portraits** — understand them with your own vision/caption/image-embedding.

This is what keeps the corpus a genuine benchmark for OCR and multimodal retrieval rather than a
solved text dump.

## Ground truth: `golden.jsonl`

One JSON object per line, aligned with general enterprise-RAG benchmark formats:

```json
{"id": "Q-C-1000-cause", "question": "What cause of loss was recorded for claim C-1000?",
 "answer": "burglary", "relevant_doc_ids": ["DOC-C-1000-ADJ", "DOC-C-1000-FNOL"],
 "query_class": "semantic", "modality": "text", "provenance": {"entity_id": "C-1000", "field": "cause"}}
```

| Field | Meaning |
|---|---|
| `id` | Stable question id. |
| `question` / `answer` | The query and its by-construction ground-truth answer. |
| `relevant_doc_ids` | **Every** document that asserts the answer (resolve via `manifest.json`). |
| `query_class` | `semantic` · `aggregation` · `multi_hop` (the reasoning shape). |
| `modality` | The input a system must read: `text` · `ocr` · `vision` · `multimodal_retrieval` · `cross_modal`. |
| `provenance` | Single-hop: `{entity_id, field}`. Multi-hop: `{hops: […]}` (the explicit chain). |

Every answer is grounded in document provenance: it is *exactly* what its cited documents state, and
`relevant_doc_ids` is *exactly* the set that asserts it (`make validate` enforces this). See
[golden/README.md](../golden/README.md).

**Multimodal coverage.** Beyond `text`, four modalities have answers that live only in a scanned or image
document, so they verify OCR / vision / multimodal-retrieval capability rather than text retrieval:

- **`ocr`** — a police-report reference number on a **scan-only** document (rendered → scanned → born-digital
  PDF *never* emitted, so its facts exist on no born-digital page).
- **`vision`** — the visibly-damaged area in an evidence photo (labelled by the seeded image prompt-spec).
- **`multimodal_retrieval`** — an on-file ID portrait, retrieved by policyholder identity.
- **`cross_modal`** — a text→image chain (find a claim from its document, then read its photo).

A leak-guard test asserts every `ocr` / `vision` / `cross_modal` answer appears on **no** born-digital page,
so those questions genuinely require the modality. Because the corpus ships **no clean-text sidecar for
scans**, a consumer must actually OCR / interpret the images — that is what keeps this a real multimodal test.

## How to score

A dependency-free reference scorer ships with the corpus so every consumer scores identically against
the labels — it scores *predictions*, it does not do retrieval:

```bash
make eval PRED=your-predictions.jsonl        # Recall@K / nDCG@K / EM / F1, broken down by query_class AND modality
python -m generator.eval --golden golden/golden.jsonl --predictions preds.jsonl --out metrics.json
```

Predictions are JSONL, one row per answered question:
`{"id": "Q-C-1000-cause", "retrieved_doc_ids": ["DOC-…", …], "answer": "burglary"}`. See
[golden/README.md](../golden/README.md) for the metric definitions and `sample/predictions.example.jsonl`.

## Guarantees

- **Deterministic.** Same `(seed, profile)` → byte-stable corpus, manifest, golden, and PII index.
- **Synthetic.** No real persons, companies, or policies; every document is marked synthetic in
  metadata and, where visible, on the page. The realistic synthetic PII is intentional redaction-test
  material — handling it is the consuming layer's job, not the corpus's.
- **Licensing.** Code/generator: MIT. Generated data + sample: CC-BY-4.0.
