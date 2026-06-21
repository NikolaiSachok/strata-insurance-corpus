# strata-insurance-corpus

> A **reproducible, synthetic, multi-format insurance document corpus** — born-digital **and** scanned
> PDFs, Word documents, spreadsheets, and photos from a fictional property-&-casualty insurer,
> **Meridian Mutual** — shipped with a **golden evaluation set produced by construction**. Built to
> exercise and benchmark document-RAG systems on *enterprise-shaped* data. Usable standalone with any
> RAG stack, or as a drop-in corpus for [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG).

**Status: 🚧 M1 + M2 complete; M3+ in progress.** The seeded generator and entity model, all born-digital
document families (policy / claim / tabular / knowledge), the manifest + provenance, and the
golden-eval set (semantic + aggregation) run end-to-end today. Scanned variants, generated images,
synthetic-PII injection, the eval harness, and the Strata-RAG adapter are scheduled (M3–M5). Design and
roadmap: **[BRIEF.md](BRIEF.md)** and the **[issues](../../issues)**.

### What runs today (M1–M2)

```bash
make sample     # -> committed sample/ slice + golden/golden.jsonl  (deterministic)
make generate   # -> full corpus/ : 305 entities, 778 documents (651 PDF + 121 Word + 4 sheets + 2 Markdown), 255 golden Qs  (gitignored)
make validate   # integrity + golden-support checks
make stats      # corpus composition (documents by format/type, golden by class)
make test       # determinism + referential-integrity suite
```

Full-corpus composition (`make stats OUT=corpus`): 651 PDF · 121 Word · 3 xlsx · 1 csv · 2 Markdown;
golden = 252 semantic + 3 aggregation. The committed `sample/` slice contains at least one of every
built doc type (enforced by a test), so the repo is fully exercisable without a full run.

Built: deterministic entity model + roster ([docs/data-model.md](docs/data-model.md)); the **policy** family
— declarations / endorsements / coverage-schedule (born-digital PDF, WeasyPrint) + full **contract in Word
`.docx`** (python-docx); the **claim** family — FNOL, adjuster report, damage/repair estimate, and settlement & denial letters
(PDF), conditioned on claim status; the **tabular** family — loss run, reserve & premium registers
(xlsx) and an agent commission summary (csv); and the **knowledge** family — underwriting guidelines &
customer FAQ (Markdown) and a claims-handling manual (docx). All renderers byte-reproducible
(`SOURCE_DATE_EPOCH` / pinned docx & xlsx packaging); `manifest.json` with per-doc provenance + sha256;
**semantic** (cause-of-loss, premium, settlement amount, lines-of-business) **and aggregation** (total open
reserve, total premium, open-claim count) golden-question classes. The doc-type × format build-out is
tracked in [docs/format-matrix.md](docs/format-matrix.md).

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

## What it will contain — Meridian Mutual (fictional P&C insurer)

Auto · Home · Small-commercial lines. The document universe maps to every real document-RAG challenge:

| Document family | Formats | RAG capability it exercises |
|---|---|---|
| Policies, declarations pages, endorsements, coverage schedules | PDF (born-digital), docx | semantic retrieval, structured extraction |
| Claims: FNOL forms, adjuster reports, estimates, settlement letters | PDF + **scanned variants** | **OCR + layout-aware chunking** |
| Evidence: damage/property photos, ID scans, police reports | **images** | **vision captioning / multimodal retrieval** |
| Loss runs, reserve & premium tables, commission sheets | Excel/CSV | **tabular / aggregation queries** |
| Underwriting guidelines, manuals, FAQ / knowledge base | Markdown, docx | semantic knowledge retrieval |
| Roster: policyholders, policies, claims, agents, adjusters | TSV | **master-data join + PII redaction** (synthetic SSNs / policy #s) |

## Design principles

- **A generator, not a data dump.** The corpus is produced by a **seeded, deterministic** pipeline
  (`make generate SEED=…`) — reproducible, parameterizable, and far more useful than a static folder.
- **Eval by construction.** Ground-truth answers + provenance are emitted *during* generation.
- **Clearly synthetic.** No real individuals or companies; documents are watermarked/metadata-tagged
  as synthetic. Any resemblance to real entities is coincidental.
- **Multi-format on purpose.** Each format is included because it poses a *distinct* RAG problem
  (scanned → OCR, spreadsheets → aggregation, photos → vision), not for variety's sake.
- **Standalone or plug-in.** Works with any RAG system; ships a [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG)
  adapter so the engine can mount it via `RAGEVAL_PLUGINS_DIR`.

## Repo layout

```
generator/   the seeded synthetic-data pipeline (model → content → render + provenance)   [M1 ✅]
sample/      a small, committed slice of the corpus (so the repo is usable without a full run) [M1 ✅]
golden/      the golden evaluation set (semantic now; aggregation + multi-hop in M4)        [M1 ✅]
adapter/     the Strata-RAG source adapter (register_adapter / register_family)             [M5 ⏳]
docs/        the data model, the format matrix, related work                                 [M1 ✅]
Makefile     generate / sample / validate / test targets                                     [M1 ✅]
```

The **full corpus** (hundreds of documents + images) is reproducible locally and will be published as a
**HuggingFace Dataset** release; only the small `sample/` is committed to git.

## Using it

- **Standalone:** `make generate` → point your RAG pipeline at `corpus/`.
- **With Strata-RAG:** install this repo, set `RAGEVAL_PLUGINS_DIR` to `adapter/` (see [BRIEF.md](BRIEF.md)).
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
