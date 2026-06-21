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
| **Evidence** | vehicle/property damage photos, ID/license scans, police report (scanned) | JPG / PNG (`/generate-image`) | vision caption / multimodal; PII on IDs | M3 | ⏳ planned |
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

### Reproducibility of non-deterministic assets (images)

AI-generated image bytes cannot be byte-stable the way PDFs/docx/xlsx are. We keep the corpus
*reproducible by construction* anyway by committing the **deterministic recipe** instead of the pixels:

- A seeded, offline **prompt-spec generator** derives, per evidence document, a complete generation recipe
  from the entity model — written to `image-prompts.jsonl` (committed, byte-stable):

  ```json
  {"doc_id": "DOC-C-1042-DAMAGE-01", "entity_ids": ["C-1042"], "kind": "vehicle_damage",
   "prompt": "front-end collision damage to a sedan, daylight, insurance evidence photo, ...",
   "negative_prompt": "...", "model": "nano-banana-pro", "params": {"aspect_ratio": "4:3", "seed": 104201},
   "caption": "Front-end damage consistent with a rear-end collision."}
  ```

- The **prompt, model id, and settings (including a per-image seed derived from the corpus seed)** are the
  committed source of truth. Anyone can re-run the same recipe to get a *closely* reproducible image; the
  manifest entry for the rendered image references its prompt-spec `doc_id`.
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
