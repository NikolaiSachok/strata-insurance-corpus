# strata-insurance-corpus — build targets. See BRIEF.md for the M1–M5 roadmap.
#
# Determinism: same SEED -> byte-stable corpus. Generation runs through `uv run`,
# which auto-syncs the venv from pyproject.toml (no manual activate needed).
SEED  ?= 42
RUN   ?= uv run
OUT   ?= corpus

.PHONY: help generate sample validate stats test clean

help:
	@echo "Targets (see BRIEF.md):"
	@echo "  generate SEED=<n>  - deterministically generate the full corpus + manifest + golden eval -> corpus/"
	@echo "  sample             - regenerate the committed sample/ slice (+ golden/golden.jsonl)"
	@echo "  validate OUT=<dir> - validate manifest/schema + that every golden Q has a supporting doc (default: corpus/)"
	@echo "  stats OUT=<dir>    - print corpus composition (documents by format/type, golden by class)"
	@echo "  test               - run the generator test suite (determinism, etc.)"
	@echo "  clean              - remove generated corpus/ + caches"

generate:
	$(RUN) python -m generator.run --seed $(SEED) --out corpus --profile full

# Committed, self-contained mini-corpus (small slice, all M1 formats). The golden
# eval is mirrored to golden/golden.jsonl as the canonical committed eval set.
sample:
	$(RUN) python -m generator.run --seed $(SEED) --out sample --profile sample
	@mkdir -p golden && cp sample/golden.jsonl golden/golden.jsonl
	@echo "[sample] wrote sample/ and mirrored golden/golden.jsonl"

validate:
	$(RUN) python -m generator.validate --out $(OUT)

stats:
	$(RUN) python -m generator.stats --out $(OUT)

test:
	$(RUN) --extra dev pytest -q

clean:
	rm -rf corpus/ .cache/ .llm-cache/
