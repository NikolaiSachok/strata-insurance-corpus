# Entity / data model + roster schema

The **spine** of the corpus. A deterministic, seeded model
([`generator/model.py`](../generator/model.py)) is generated *first*; every document is a
rendering of it, so cross-document facts are consistent and the golden answers are knowable
by construction. JSON Schema for all of this is emitted to `<out>/schema/` at generation time
([`generator/schema.py`](../generator/schema.py)).

## Company

A mid-size US property-&-casualty mutual insurer, **Meridian Mutual** (fictional). Lines of
business: **personal auto**, **homeowners**, **small-commercial (BOP)**. All entities are
synthetic and clearly labelled; the synthetic tax id uses the never-issued `9NN-NN-NNNN`
area prefix so it can never collide with a real SSN.

## Temporal anchoring

All dates derive from a fixed `ANCHOR` (`2024-07-01`) — **never** from the wall clock — so the
model is byte-stable across days and machines. Policies are 12-month terms within a ~2-year
window around the anchor; each claim's date-of-loss falls inside its policy term.

## Entities

| Entity | Id format | Key fields | Foreign keys |
|---|---|---|---|
| **Policyholder** | `PH-00001` | name, dob, email, phone, street/city/state/zip, `synthetic_tax_id` | — |
| **Agent** | `AG-001` | name, agency, region | — |
| **Adjuster** | `AD-001` | name, specialty | — |
| **Policy** | `PA-/HO-/BOP-0000001` | line, effective/expiry dates, annual_premium, limits, deductible, endorsements | `holder_id` → Policyholder, `agent_id` → Agent |
| **Claim** | `C-1000` | line, date_of_loss, reported_date, status, cause, reserve, paid, narrative_seed | `policy_id` → Policy, `holder_id` → Policyholder, `adjuster_id` → Adjuster |

- **Lines:** `personal_auto`, `homeowners`, `bop`. The policy id prefix encodes the line
  (`PA`/`HO`/`BOP`).
- **Claim status:** `closed` (~60%), `open` (~30%), `denied` (~10%). Reserve/paid follow status
  (open → positive reserve + partial paid; closed → reserve 0, paid set; denied → both 0), so
  aggregation golden questions (M4) have knowable answers.
- **Limits** are line-shaped: auto carries BI-per-person / BI-per-accident / PD; homeowners
  carries dwelling / personal-property / personal-liability; BOP carries building / BPP /
  general-liability.

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

## Determinism contract

Same `(seed, profile)` → byte-identical `model.json` and `roster.tsv` **across environments**.
Rendered PDFs/`.docx`/`.xlsx` and **scanned `.jpg`** variants are byte-identical too (PDF via
`SOURCE_DATE_EPOCH`, docx/xlsx via pinned dates + normalized zip, scans via a per-document seed), but
only with the **same render toolchain** — WeasyPrint + cairo/pango, python-docx, openpyxl, and for scans
pypdfium2 + Pillow (libjpeg); the committed `sample/` artifacts were rendered with the versions pinned in
[`uv.lock`](../uv.lock). Enforced by [`tests/test_determinism.py`](../tests/test_determinism.py)
(structured-output byte-stability, plus PDF and docx render-path byte-stability).
