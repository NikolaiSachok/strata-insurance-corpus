# generator/

The seeded, deterministic synthetic-data pipeline (see [BRIEF.md](../BRIEF.md) → "Generation pipeline"
and [docs/data-model.md](../docs/data-model.md)).

## Usage

```bash
make generate SEED=42      # full corpus -> corpus/   (gitignored)
make sample                # committed slice -> sample/ (+ golden/golden.jsonl)
make validate OUT=corpus   # integrity + golden-support checks
make test                  # determinism + integrity suite
# or directly:
uv run python -m generator.run --seed 42 --out corpus --profile full
uv run python -m generator.run --seed 42 --out /tmp/m --profile slice --no-render  # model-only
```

`--profile` is one of `full` / `sample` / `slice`. Same `(seed, profile)` → byte-stable output.

## Modules

| Module | Status | Role |
|---|---|---|
| `model.py` | ✅ M1 | seed → entities (policyholders, agents, adjusters, policies, claims) + `roster.tsv` |
| `schema.py` | ✅ M1 | JSON Schema for `model.json` + roster column contract → `schema/` |
| `content.py` | ✅ M1 | per-document view-models / prose (deterministic templates; LLM seam for M2) |
| `render/pdf.py` | ✅ M1 | HTML (Jinja2) → born-digital PDF (WeasyPrint), reproducible via `SOURCE_DATE_EPOCH` |
| `render/docx.py` | ✅ #5 | python-docx → reproducible `.docx` (pinned dates + normalized zip) |
| `provenance.py` | ✅ M1 | per-doc `{entity_id, field, value}` assertions + content hashes |
| `manifest.py` | ✅ M1 | emit `manifest.json` listing every document + provenance |
| `golden.py` | ✅ M1 | golden eval (semantic class) → `golden.jsonl` |
| `tabular.py` | ✅ #7 | model → loss run / reserve / premium / commission tables + aggregates |
| `knowledge.py` | ✅ #8 | underwriting guidelines / claims manual / customer FAQ content |
| `render/sheets.py` | ✅ #7 | tables → reproducible xlsx + csv |
| `render/markdown.py` | ✅ #8 | KB docs → Markdown |
| `render/_repro.py` | ✅ #7 | shared deterministic zip packaging (docx + xlsx) |
| `run.py` | ✅ M1 | pipeline orchestrator + CLI |
| `validate.py` | ✅ M1 | referential integrity, file/sha checks, golden-support checks |
| `stats.py` | ✅ #9 | corpus composition summary (`make stats`) |
| `render/scan.py` | ✅ #10 | PDF → degraded "scanned" JPG (pypdfium2 + seeded Pillow effects), forces OCR |
| `imageprompts.py` | ✅ #11 | per-claim evidence-photo **prompt-specs** → `image-prompts.jsonl` (pixels via `/generate-image`, rendered for sample/) |
| `render/image.py` | ✅ #11 | finalize a rendered evidence image: downscale + embed an EXIF synthetic marker |

## Evidence images — done criteria

The corpus is **synthetic but realistic**: synthetic faces, vehicle makes, and invented plates are
*allowed* — they're the realistic PII a redaction system is benchmarked on, and PII handling belongs in
the consuming RAG layer, not the source documents. So before an image enters `sample/` it must only be:
(1) **visually verified** NOT to depict a **real identifiable individual** (e.g. a public figure) or a
**real named company** as the claim party; and (2) finalized through `render/image.py` so it carries the
**EXIF synthetic marker**. The committed reproducible artifact is the prompt-spec in `image-prompts.jsonl`;
the full-corpus pixels are produced on-demand for the HF release.

## Native dependency (PDF)

WeasyPrint needs cairo / pango / gdk-pixbuf. On macOS these come from Homebrew
(`brew install cairo pango gdk-pixbuf libffi`); `render/pdf.py` points the dynamic loader at the
Homebrew prefix automatically. On Debian/Ubuntu: `apt-get install libpango-1.0-0 libpangocairo-1.0-0`.
