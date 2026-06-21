# generator/

The seeded, deterministic synthetic-data pipeline (see [BRIEF.md](../BRIEF.md) → "Generation pipeline").

Planned modules:
- `model.py` — seed → entities (policyholders, policies, claims, agents, adjusters) + roster TSV.
- `content.py` — per-document LLM prose conditioned on entity facts; cached by (seed, doc_id).
- `render/` — `pdf.py`, `docx.py`, `xlsx.py`, `scan.py` (scan effects → OCR), `image.py` (`/generate-image`).
- `provenance.py` — record which entity/field each document asserts (feeds the golden eval).
- `manifest.py` / `run.py` — emit `manifest.json`; CLI entrypoint (`python -m generator.run --seed N`).

Implemented across milestones M1–M3. Empty until then.
