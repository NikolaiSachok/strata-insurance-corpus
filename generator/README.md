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
| `run.py` | ✅ M1 | pipeline orchestrator + CLI |
| `validate.py` | ✅ M1 | referential integrity, file/sha checks, golden-support checks |
| `render/{xlsx,scan,image}.py` | ⏳ M2–M3 | xlsx/scan-effect/image renderers |

## Native dependency (PDF)

WeasyPrint needs cairo / pango / gdk-pixbuf. On macOS these come from Homebrew
(`brew install cairo pango gdk-pixbuf libffi`); `render/pdf.py` points the dynamic loader at the
Homebrew prefix automatically. On Debian/Ubuntu: `apt-get install libpango-1.0-0 libpangocairo-1.0-0`.
