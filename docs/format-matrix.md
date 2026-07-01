# Document-type × format matrix

The generator emits documents across six **families**. Each family renders to one or
more **formats** chosen to exercise a specific document-RAG capability. This is the
contract for what `make generate` produces; it is the build-out plan for M1–M3.

Every document is tagged with: `doc_id`, `doc_type`, `format`, `is_scanned`,
`synthetic: true`, the `entity_id`(s) it is about, and a `provenance` block (the
entity/field facts it asserts). The top-level [`manifest.json`](../generator/manifest.py)
lists everything; see [data-model.md](data-model.md) for the entity model those
documents render.

## Matrix

| Family | Items | Format(s) | RAG capability targeted | Milestone | Status |
|---|---|---|---|---|---|
| **Policy** | policy contract, declarations page, endorsements, coverage schedule | PDF (born-digital), docx | semantic + structured extraction | M1 / M2 | ✅ declarations / endorsements / coverage-schedule (PDF) + full contract (**docx**) — all built (#5) |
| **Claim** | FNOL form, adjuster report, damage/repair estimate, settlement letter, denial letter | PDF + **scanned variant** | OCR, layout-aware chunking | M1 / M2 / M3 | ✅ FNOL (M1) + adjuster report / estimate / settlement & denial letters (PDF, #6); **scanned variants** of FNOL + letters (JPG, #10) |
| **Evidence** | vehicle/property/commercial damage photos, accident statement, police report | JPG / PNG (`/generate-image`), PDF, **scan-only JPG** | vision caption / multimodal; OCR | M3 / M5 | ✅ damage photos — committed **prompt-spec** (`image-prompts.jsonl`) + rendered **sample** pixels (#11); ✅ **accident statement** — own EAS-inspired Motor form (bundled handwriting font + checkmarks + inline-SVG schematic, born-digital + scanned variant) (#11); ✅ **police report** — **scan-only** Motor OCR target with no born-digital twin (#41) |
| **Identity** | policyholder ID card (KYC on-file copy) | PDF + **scanned variant**; embedded JPG portrait | OCR + MRZ parsing, face/PII redaction, layout | M3 | ✅ born-digital card with name / document no. / national identifier / DOB / address + ICAO-9303 TD1 **MRZ**; portrait is a committed **prompt-spec** + rendered **sample** pixels; **scanned variant** for OCR (#11) |
| **Tabular** | loss run, reserve register, premium register, agent commission summary | XLSX / CSV | aggregation / metadata queries | M2 | ✅ loss run / reserve register / premium register (**xlsx**) + commission summary (**csv**) — built (#7) |
| **Knowledge** | underwriting guidelines, claims handling manual, customer FAQ/KB | Markdown, docx | semantic KB retrieval | M2 | ✅ underwriting guidelines + customer FAQ (**Markdown**) + claims handling manual (**docx**) — built (#8) |
| **Correspondence** | customer letters/emails, status notices | docx / txt / eml | retrieval over informal text | — (unscheduled) | ⏳ planned |

Legend: ✅ implemented · ⏳ planned (issue open). This table is kept honest — it
describes only what is built plus what is explicitly scheduled.

## Format decisions

- **Born-digital PDF** — HTML/CSS templates (`generator/render/templates/`) rendered with
  **WeasyPrint**. Reproducibility is pinned via `SOURCE_DATE_EPOCH` (derived from the model
  anchor date) so the same content yields byte-identical PDFs. Chosen over LaTeX/ReportLab
  for templating ergonomics and CSS paged-media support.
- **Scanned variant** (#10) — a born-digital PDF is rasterized (pypdfium2) and re-rendered through seeded
  scan effects (grayscale, blur, skew, paper noise, lossy JPEG) to *force real OCR* downstream. Both the
  clean ground-truth document and the degraded JPG are kept; the scanned record carries `is_scanned: true`
  and `scanned_of: <clean doc_id>`, so OCR output can be scored against the known text. Effects are seeded,
  so the scan is byte-reproducible.
- **Scan-only variant** (#41) — a stronger OCR target: the born-digital PDF is a *render intermediate* that
  is **deleted** after rasterization, so the document exists in the corpus **only** as a scan (`is_scanned:
  true`, **no** `scanned_of`). Its facts therefore appear on no born-digital page — used for the police
  report, whose reference number grounds an `ocr` golden question that genuinely requires reading the image.
- **docx** — `python-docx` (policy contract, #5). Reproducibility: core-property dates are pinned and the
  package zip is re-packed with normalized member timestamps, so the same content yields a byte-identical
  `.docx`. **xlsx** — `openpyxl` (#7); reproducible via the same normalized-zip path, plus a pin of the
  `dcterms:modified` timestamp openpyxl stamps at save. **csv / Markdown** — UTF-8 text (inherently
  deterministic); the knowledge base (#8) renders to Markdown and one `.docx` from a shared
  `{title, intro, sections}` structure.
- **Images (M3)** — generated via the `/generate-image` skill (Nano Banana) for damage/property
  photos and ID/form scans, each captioned and recorded in the manifest. Image **pixels are not
  byte-deterministic**, so the committed, reproducible artifact is the **prompt spec**, not the image
  (see below).

### Reproducibility of non-deterministic assets (images) — built in #11

AI-generated image bytes cannot be byte-stable the way PDFs/docx/xlsx are. We keep the corpus
*reproducible by construction* anyway by committing the **deterministic recipe** instead of the pixels
([`generator/imageprompts.py`](../generator/imageprompts.py)):

- A seeded, offline **prompt-spec generator** derives, per claim, a complete generation recipe from the
  entity model (cause × line × country) — written to `image-prompts.jsonl` (committed, byte-stable):

  ```json
  {"doc_id": "DOC-C-1000-EVIDENCE", "claim_id": "C-1000", "line": "homeowners", "cause": "kitchen_fire",
   "country": "IE", "kind": "property_damage", "path": "evidence/C-1000-evidence.jpg",
   "model": "gemini-3.1-flash-image", "params": {"aspect_ratio": "4:3", "resolution": "1K", "seed": 4201347},
   "prompt": "A candid amateur smartphone photo ... fire and smoke damage in a domestic kitchen ...",
   "negative_prompt": "no readable number plates ...", "caption": "... — Household claim C-1000 (Ireland)."}
  ```

- The **prompt, model id, and settings (incl. a per-image seed derived from the corpus seed)** are the
  committed source of truth. Each evidence image also gets a **manifest record** carrying the prompt-spec
  plus a `rendered` flag: `rendered: true` (+ sha256) for the committed `sample/` pixels, `rendered: false`
  for the full corpus (where only the recipe is committed; pixels are produced on-demand for the HF release).
- The rendered pixels live in the gitignored `corpus/` and the HuggingFace release (like all heavy output);
  only the prompt spec + captions are committed. This mirrors how LLM prose is cached by `(seed, doc_id)`:
  the *instructions* are reproducible even where the *output* is not bit-exact.

## Per-document metadata (manifest schema)

Each entry in `manifest.json → documents[]`:

| Field | Meaning |
|---|---|
| `doc_id` | Stable document id, e.g. `DOC-C-1000-FNOL`. |
| `doc_type` | `policy_contract` \| `fnol` \| … (one per matrix item). |
| `format` | `pdf` \| `docx` \| `xlsx` \| `png` \| … |
| `path` | Path relative to the corpus root. |
| `is_scanned` | `true` for OCR-forcing scanned variants. |
| `synthetic` | Always `true`. |
| `entity_ids` | Every entity the document is about (join keys into the roster). |
| `sha256` | Content hash (lets `validate` confirm byte-for-byte integrity). |
| `provenance[]` | `{entity_id, field, value}` facts the document asserts — the basis of the golden eval. |
