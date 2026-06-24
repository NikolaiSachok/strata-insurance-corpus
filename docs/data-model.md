# Entity / data model + roster schema

The **spine** of the corpus. A deterministic, seeded model
([`generator/model.py`](../generator/model.py)) is generated *first*; every document is a
rendering of it, so cross-document facts are consistent and the golden answers are knowable
by construction. JSON Schema for all of this is emitted to `<out>/schema/` at generation time
([`generator/schema.py`](../generator/schema.py)).

## Company

A mid-size **pan-European** property-&-casualty mutual insurer, **Meridian Mutual Insurance SE**
(fictional). Lines of business: **Motor**, **Household**, **small-commercial (Commercial)**. Policyholders
are distributed across six Eurozone countries (**DE, FR, ES, IT, NL, IE**) with locale-correct
names/addresses (Faker locales); amounts are **€**, dates display **DD/MM/YYYY**. All entities are synthetic
and clearly labelled; each policyholder's `national_id` is **format-shaped but deliberately invalid** per
country (see [`generator/identity.py`](../generator/identity.py)) — it violates the official checksum or
uses a reserved value, so it can never match a real person's identifier.

## Temporal anchoring

All dates derive from a fixed `ANCHOR` (`2024-07-01`) — **never** from the wall clock — so the
model is byte-stable across days and machines. Policies are 12-month terms within a ~2-year
window around the anchor; each claim's date-of-loss falls inside its policy term.

## Entities

| Entity | Id format | Key fields | Foreign keys |
|---|---|---|---|
| **Policyholder** | `PH-00001` | name, dob, email, phone, street/city/postcode, `country`, `national_id` | — |
| **Agent** | `AG-001` | name, agency, region | — |
| **Adjuster** | `AD-001` | name, specialty | — |
| **Policy** | `MOT-/HH-/COM-0000001` | line, effective/expiry dates, annual_premium, limits, deductible, endorsements, **vehicle** (Motor only: make/model/year/colour/synthetic reg) | `holder_id` → Policyholder, `agent_id` → Agent |
| **Claim** | `C-1000` | line, date_of_loss, reported_date, status, cause, reserve, paid, narrative_seed | `policy_id` → Policy, `holder_id` → Policyholder, `adjuster_id` → Adjuster |

- **Lines:** internal keys `personal_auto`, `homeowners`, `bop`, shown as **Motor / Household / Commercial**;
  the policy id prefix encodes the line (`MOT`/`HH`/`COM`).
- **Claim status:** `closed` / `open` / `denied` (the first three claims are forced to cover all three so
  even the small sample exercises every status-dependent document; the rest are weighted ~60/30/10).
  Reserve/paid follow status (open → positive reserve + partial paid; closed → reserve 0, paid set;
  denied → both 0), so aggregation golden questions have knowable answers.
- **Limits** are line-shaped (amounts in €): Motor carries BI-per-person / BI-per-accident / PD; Household
  carries dwelling / personal-property / personal-liability; Commercial carries building / BPP /
  general-liability.
- **Identity document (#11):** every policyholder has an on-file **ID card** (KYC copy) surfacing their
  real synthetic PII — `name`, `national_id`, `dob`, address — plus an ICAO-9303 TD1 **machine-readable
  zone** and a synthetic AI portrait. This drives an *identity* semantic golden class (`Q-PH-*-national-id`:
  the policyholder's national identifier, supported by their ID card). Gender is **not** modelled — the
  portrait's apparent gender is inferred best-effort from the given name for realism, not a stored fact.

## `model.json`

Canonical structured output: `{ meta, policyholders[], agents[], adjusters[], policies[],
claims[] }`, emitted with sorted keys and a trailing newline (diffable in CI). `meta` records
`seed`, `profile`, `anchor_date`, the `synthetic` marker, and per-entity `counts`. Validated
against `schema/model.schema.json`.

## `roster.tsv` — the join target

A flat, **id-keyed master-data index** — the table the RAG engine joins to for "who/what owns
this" questions (mirrors Strata-RAG's roster / `register_family` pattern). One header row plus
one row per entity, tab-separated, UTF-8, fixed column order, grouped by type then id:

| Column | Meaning |
|---|---|
| `id` | Primary key (`PH-`/`AG-`/`AD-`/policy/claim id). |
| `type` | `policyholder` \| `agent` \| `adjuster` \| `policy` \| `claim`. |
| `name` | Human-readable label. |
| `line` | Line of business for policy/claim rows; empty otherwise. |
| `parent_id` | Join key to the owning entity (`policy.holder_id`, `claim.policy_id`). |
| `status` | Claim status; empty for other types. |
| `detail` | Free-text supplementary attributes. |

Schema: `schema/roster.schema.json`.

## Profiles

Generation scale is selected by `--profile`:

| Profile | Holders | Agents | Adjusters | Policies | Claims | Use |
|---|---|---|---|---|---|---|
| `full` | 80 | 15 | 10 | 120 | 80 | the full corpus (`make generate`) |
| `sample` | 6 | 3 | 2 | 5 | 5 | the committed `sample/` slice (`make sample`) |
| `slice` | 1 | 1 | 1 | 1 | 1 | the M1 vertical slice (1 of everything, end-to-end) |

## Provenance & golden grounding (`manifest.json` → `golden.jsonl`)

Every document records the `(entity_id, field, value)` facts it asserts (its `provenance` block in
`manifest.json`). [`provenance.py`](../generator/provenance.py) inverts these into a **provenance index**
`(entity_id, field) → [(doc_id, value)]`, and the golden set is built entirely from it: a question about
`(entity, field)` takes its **answer** from the asserted value and its **`relevant_doc_ids`** from *every*
document that asserts the fact (so a "cause of loss" answer cites both the FNOL and the adjuster report).
Corpus-level aggregates (open reserve, total premium, open-claim count) and the lines-of-business fact are
asserted on the registers / guidelines that state them, so aggregation and KB questions are grounded the
same way. `make validate` checks the loop: each golden answer must equal what every cited document asserts.

## Redaction ground truth (`pii-index.jsonl`)

The corpus carries realistic synthetic PII on purpose — it is the material a redaction/PII-detection
layer is benchmarked on (handling that PII is the consuming RAG layer's job, not the source corpus).
Every PII occurrence is catalogued as one JSONL span so a detector can be **scored** against known truth:

```json
{"doc_id":"DOC-PH-00001-IDCARD","doc_type":"id_card","is_scanned":false,"modality":"text",
 "entity_id":"PH-00001","entity_type":"policyholder","pii_type":"NATIONAL_ID","field":"national_id","value":"133890832"}
```

- **`pii_type`** ∈ `PERSON_NAME`, `ADDRESS`, `DATE_OF_BIRTH`, `EMAIL_ADDRESS`, `PHONE_NUMBER`,
  `NATIONAL_ID`, `POLICY_NUMBER`, `CLAIM_NUMBER`, `VEHICLE_REGISTRATION`, `ID_DOCUMENT_NUMBER`, `MRZ`, `FACE`.
- **`modality`** — `text` (born-digital), `image_text` (the same span on a scanned variant — an OCR+redact
  target), or `image_region` (the ID portrait `FACE`, the only value-less span).
- **`entity_type`** ties each span to its owner (`policyholder` / `agent` / `adjuster` / `policy` / `claim`,
  or `third_party` for the doc-local other-party PII on a collision accident statement).
- The index is a **pure function of the model** (deterministic, decoupled from render-library versions).
  Accuracy is enforced by [`tests/test_pii.py`](../tests/test_pii.py), which extracts each rendered
  document's text and asserts the catalogue is **accurate** (every text span appears) and **complete**
  (every known model PII value present in a document is catalogued).

## Determinism contract

Same `(seed, profile)` → byte-identical `model.json` and `roster.tsv` **across environments and processes**.
(A few Faker locale providers — e.g. `it_IT` `city()` — select from sets whose order is
`PYTHONHASHSEED`-dependent, so generation pins `PYTHONHASHSEED=0`: the Makefile exports it and `run.py`
re-execs with it. A cross-process test guards this.)
Rendered PDFs/`.docx`/`.xlsx` and **scanned `.jpg`** variants are byte-identical too (PDF via
`SOURCE_DATE_EPOCH`, docx/xlsx via pinned dates + normalized zip, scans via a per-document seed), but
only with the **same render toolchain** — WeasyPrint + cairo/pango, python-docx, openpyxl, and for scans
pypdfium2 + Pillow (libjpeg); the committed `sample/` artifacts were rendered with the versions pinned in
[`uv.lock`](../uv.lock). Enforced by [`tests/test_determinism.py`](../tests/test_determinism.py)
(structured-output byte-stability, plus PDF and docx render-path byte-stability).
