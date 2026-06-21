# Related work — why a new corpus (not a reuse)

This corpus deliberately stands on prior art. None of the following offers the combination we need
(**insurance depth × full real-world format spectrum × ground-truth eval**), but each informs the design.

## Insurance-specific synthetic data
- **RISC** — *Generating Realistic Synthetic Bilingual Insurance Contracts* (arXiv:2304.04212). 10k auto
  contracts, EN/FR, `.txt`. → Reuse: contract-language realism for our policy documents. (Single format,
  single doc-type — not a multi-format corpus.)
- **SynthETIC** — *An individual insurance claim simulator with feature control* (arXiv:2008.05693). CRAN R
  package. → Reuse: claims/ledger structure + actuarial plausibility for our loss runs and reserves.
  (Tabular only — no documents.)
- **Generative Synthesis of Insurance Datasets** (arXiv:1912.02423), driver-telematics synthesis
  (arXiv:2102.00252) — tabular/actuarial; out of scope as documents.

## Multi-format enterprise RAG benchmarks (methodology)
- **RAG-Multi-Corpus benchmark** — fictional organizations, multi-format (PDF/MD/HTML/DOCX/PPTX), 786 QA
  pairs. → Closest structural precedent; **align our golden-set format with it** for comparability. (No
  images / spreadsheets / scanned-OCR; not insurance-deep.)
- **EnterpriseDocBench** (arXiv:2604.26382) — parsing→indexing→retrieval→generation eval on permissively
  licensed docs across six domains. → Borrow evaluation rigor.
- **ViDoRe v2** — visual document retrieval benchmark (harder, multilingual). → Reference for the
  image/visual-document retrieval portion.

## Document realism / OCR
- **ACORD forms** — industry-standard insurance form layouts. → Model FNOL / certificate / loss-run layouts.
- **OCR-IDL / GutenOCR** (arXiv:2601.14490) — noisy business documents (IDs, invoices, claims) with stamps,
  handwriting, capture artifacts. → Reference for realistic scan effects.

## The contribution
Insurance-domain depth, the *full* format spectrum (born-digital + scanned PDFs, docx, Excel, photos), and a
golden eval set that's correct **by construction** — a combination none of the above provides.
