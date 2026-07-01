# strata-insurance-corpus

[![CI](https://github.com/NikolaiSachok/strata-insurance-corpus/actions/workflows/ci.yml/badge.svg)](https://github.com/NikolaiSachok/strata-insurance-corpus/actions/workflows/ci.yml)

> A **reproducible, synthetic, multi-format insurance document corpus** — born-digital **and** scanned
> PDFs, Word documents, spreadsheets, and photos from a fictional property-&-casualty insurer,
> **Meridian Mutual** — shipped with a **golden evaluation set produced by construction**. Built to
> exercise and benchmark document-RAG systems on *enterprise-shaped* data. Usable standalone with any
> RAG stack, or as a drop-in corpus for [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG).

**Status: 🚧 M1–M4 complete; M5 in progress.** The seeded generator and entity model, all born-digital
document families (policy / claim / tabular / knowledge), **scanned (OCR-target) variants** of the claim
forms/letters, **AI evidence photos + identity cards (ID scans) with synthetic portraits**, a
**redaction ground-truth index** (every PII span catalogued), the manifest + provenance, the
golden-eval set (semantic + aggregation + multi-hop **+ multimodal: OCR / vision / multimodal-retrieval /
cross-modal**), and a **reference eval harness** (Recall@K / nDCG / EM / F1) run end-to-end today. **This
is a data vendor** — it ships the data + ground truth and is engine-agnostic (see
[docs/data-card.md](docs/data-card.md), the ingestion contract); consuming RAG systems own ingestion.
**CI** (reproducibility + a committed-sample drift-check + full validate) runs on every PR and on pushes to
`main`; a HuggingFace release remains (M5). Design and roadmap: **[BRIEF.md](BRIEF.md)** and the **[issues](../../issues)**.

### What runs today

```bash
make sample     # -> committed sample/ slice + golden/golden.jsonl  (deterministic)
make generate   # -> full corpus/ : 305 entities, 1297 documents (1137 born-digital+scanned + 160 AI images as committed prompt-specs), 671 golden Qs, 6469 PII spans  (gitignored)
make validate   # integrity + golden-support checks
make stats      # corpus composition (documents by format/type, golden by class)
make eval       # score predictions vs golden (Recall@K/nDCG/EM/F1); no PRED -> oracle self-check
make test       # determinism + referential-integrity suite
```

Full-corpus composition (`make stats OUT=corpus`): 750 PDF · 121 Word · 3 xlsx · 1 csv · 2 Markdown ·
260 scanned JPG · 160 AI images — 80 evidence photos + 80 ID portraits (committed as seeded
**prompt-specs** in `image-prompts.jsonl`; pixels rendered for the `sample/` slice, on-demand for the HF
release). The 260 scans include 19 **scan-only** police reports (no born-digital twin — genuine OCR
targets). Golden = **671 questions**: 447 text (364 semantic + 3 aggregation + 80 multi-hop) + 224
**multimodal** (19 OCR + 80 vision + 80 multimodal-retrieval + 45 cross-modal — cross-modal is emitted only
for single-claim policies, so its policy-keyed question stays unambiguous); **6,469 PII spans**
catalogued in `pii-index.jsonl`. The committed `sample/` slice contains at least one of every built doc
type and every golden modality (enforced by tests), so the repo is fully exercisable without a full run.

**Redaction ground truth (`pii-index.jsonl`).** The corpus deliberately contains realistic synthetic
PII — names, addresses, dates of birth, phone/email, national identifiers, vehicle plates, ID-card
numbers + machine-readable zones, and synthetic faces (PII *handling* is the consuming RAG layer's job,
not the source corpus). So every PII occurrence is published as a machine-readable span — `doc_id`,
`pii_type`, source `field`, exact `value`, and `modality` (text / image_text / image_region) — letting a
redaction/PII-detection system be **scored** against known ground truth. It is a pure function of the
model (deterministic), and a test extracts each rendered document's text to prove the catalogue is both
accurate (no false spans) and complete (no missed model PII).

Built: deterministic entity model + roster ([docs/data-model.md](docs/data-model.md)); the **policy** family
— declarations / endorsements / coverage-schedule (born-digital PDF, WeasyPrint) + full **contract in Word
`.docx`** (python-docx); the **claim** family — FNOL, adjuster report, damage/repair estimate, and settlement & denial letters
(PDF), conditioned on claim status; the **tabular** family — loss run, reserve & premium registers
(xlsx) and an agent commission summary (csv); and the **knowledge** family — underwriting guidelines &
customer FAQ (Markdown) and a claims-handling manual (docx). All renderers byte-reproducible
(`SOURCE_DATE_EPOCH` / pinned docx & xlsx packaging); `manifest.json` with per-doc provenance + sha256;
**semantic** (cause-of-loss, premium, settlement amount, insured vehicle, national identifier, lines-of-business),
**aggregation** (total open reserve, total premium, open-claim count), **multi-hop / cross-document**
(e.g. *"the annual premium for the policy under which claim C was filed"* — a fact on no claim document, so
it must join the FNOL to the declarations), **and multimodal** — **OCR** (a police-report reference on a
**scan-only** document), **vision** (the visibly-damaged area in an evidence photo), **multimodal-retrieval**
(an on-file ID portrait), and **cross-modal** (join a claim document to its photo) — golden-question classes,
each **grounded in document provenance** — built from the `(entity, field, value)` facts each document asserts
(the seeded image prompt-spec is the by-construction label), so a golden answer is exactly what its cited
documents state and a multi-hop answer's chain is explicit (enforced by `make validate`). A leak-guard test
proves each OCR/vision answer lives on **no** born-digital page, so those questions genuinely require the
modality. A dependency-free **reference
eval harness** (`generator/eval.py`, `make eval`) scores a system's predictions against the golden set —
Recall@K / nDCG@K / exact-match / token-F1, broken down by query class **and modality** (so OCR / vision /
retrieval capability is scored separately) — so the corpus is usable standalone
with any RAG stack. The doc-type × format build-out is tracked in [docs/format-matrix.md](docs/format-matrix.md).

---

## Why this exists

Synthetic insurance data already exists — but not in the shape document-RAG actually needs:

- **Actuarial/tabular** synthetic data (e.g. SynthETIC) models *claims numbers*, not documents.
- **Single-format text** sets (e.g. RISC's 10k auto contracts) cover one doc type in `.txt`.
- General **multi-format RAG benchmarks** exist (fictional orgs, PDF/DOCX/PPTX) but aren't
  insurance-deep and omit **scanned/OCR, spreadsheets, and photos**.

No openly available corpus combines **insurance-domain depth** with the **full real-world format
spectrum** (born-digital + scanned PDFs, docx, Excel, images) **and** a **trustworthy golden eval set**.
That's the gap this fills. And because every byte is **generated**, two things follow for free:

1. **It's fully shareable** — synthetic, no real people, no private data, redistributable.
2. **The eval set is ground-truth *by construction*** — generation records which document/field answers
   which question, so the golden Q→A labels are correct, not crowd-guessed.

## What it will contain — Meridian Mutual Insurance SE (fictional pan-European P&C insurer)

Motor · Household · Small-commercial lines, with policyholders across six Eurozone countries (DE/FR/ES/IT/NL/IE),
€ amounts, and DD/MM/YYYY dates. The document universe maps to every real document-RAG challenge:

| Document family | Formats | RAG capability it exercises |
|---|---|---|
| Policies, declarations pages, endorsements, coverage schedules | PDF (born-digital), docx | semantic retrieval, structured extraction |
| Claims: FNOL forms, adjuster reports, estimates, settlement letters | PDF + **scanned variants** | **OCR + layout-aware chunking** |
| Evidence: damage/property photos, ID scans, police reports | **images** | **vision captioning / multimodal retrieval** |
| Loss runs, reserve & premium tables, commission sheets | Excel/CSV | **tabular / aggregation queries** |
| Underwriting guidelines, manuals, FAQ / knowledge base | Markdown, docx | semantic knowledge retrieval |
| Roster: policyholders, policies, claims, agents, adjusters | TSV | **master-data join + PII redaction** (synthetic national IDs / policy #s) |

## Design principles

- **A generator, not a data dump.** The corpus is produced by a **seeded, deterministic** pipeline
  (`make generate SEED=…`) — reproducible, parameterizable, and far more useful than a static folder.
- **Eval by construction.** Ground-truth answers + provenance are emitted *during* generation.
- **Clearly synthetic.** No real individuals or companies; documents are watermarked/metadata-tagged
  as synthetic. Any resemblance to real entities is coincidental.
- **Multi-format on purpose.** Each format is included because it poses a *distinct* RAG problem
  (scanned → OCR, spreadsheets → aggregation, photos → vision), not for variety's sake.
- **Engine-agnostic data vendor.** Works with any RAG system; the corpus ships data + ground truth and
  prescribes no processing. Ingestion (parsing, OCR, chunking, retrieval, vision) is the consuming system's
  job — see [docs/data-card.md](docs/data-card.md). It composes with
  [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG), whose own agent writes the adapter on its side.

## Repo layout

```
generator/   the seeded synthetic-data pipeline (model → content → render + provenance)   [M1 ✅]
sample/      a small, committed slice of the corpus (so the repo is usable without a full run) [M1 ✅]
golden/      the golden evaluation set (semantic + aggregation + multi-hop) + reference eval harness   [M4 ✅]
docs/        the data card (ingestion contract), data model, format matrix, related work     [M1 ✅]
Makefile     generate / sample / validate / test targets                                     [M1 ✅]
.github/     CI: test suite + committed-sample drift-check + full generate/validate           [M5 ✅]
```

The **full corpus** (hundreds of documents + images) is reproducible locally and will be published as a
**HuggingFace Dataset** release; only the small `sample/` is committed to git.

## Using it

- **Any RAG engine:** `make generate` → point your pipeline at `corpus/`; the
  [data card](docs/data-card.md) is the ingestion contract (files, ground-truth structure, scoring).
- **With Strata-RAG:** hand it the corpus; its own agent writes the adapter on its side (this repo ships
  no engine glue).
- **Just the data:** download the published HuggingFace dataset (planned).

## Related work (why a new corpus, not a reuse)

This corpus stands on prior art rather than ignoring it: contract-language realism informed by **RISC**
(synthetic auto contracts); claims/ledger structure informed by **SynthETIC**; the multi-format +
fictional-organization shape and **evaluation methodology** aligned with general enterprise-RAG benchmarks
(**RAG-Multi-Corpus**, **EnterpriseDocBench**) and visual-document retrieval (**ViDoRe v2**); scanned-form
realism modeled on industry-standard **ACORD** layouts and noisy-business-document research (OCR-IDL). The
contribution is the *combination* none of them offer: insurance depth × full format spectrum × ground-truth
eval. Full citations in [BRIEF.md](BRIEF.md).

## License

Code/generator: **MIT** ([LICENSE](LICENSE)). Generated data + sample: **CC-BY-4.0**. **All data is
synthetic** — no real persons, policies, or companies; resemblance to real entities is coincidental.
