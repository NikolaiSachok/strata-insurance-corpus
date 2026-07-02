# strata-insurance-corpus — build targets. See BRIEF.md for the M1–M5 roadmap.
#
# Determinism: same SEED -> byte-stable corpus. Generation runs through `uv run`,
# which auto-syncs the venv from pyproject.toml (no manual activate needed).
SEED  ?= 42
RUN   ?= uv run
OUT   ?= corpus

# Pin the hash seed: some Faker locale providers (e.g. it_IT city) select from sets whose
# iteration order is PYTHONHASHSEED-dependent, which would otherwise vary model.json across
# processes. run.py re-execs with this too, so direct invocation is covered.
export PYTHONHASHSEED := 0

.PHONY: help generate sample validate stats eval test clean

help:
	@echo "Targets (see BRIEF.md):"
	@echo "  generate SEED=<n>  - deterministically generate the full corpus + manifest + golden eval -> corpus/"
	@echo "  sample             - regenerate the committed sample/ slice (+ golden/golden.jsonl)"
	@echo "  validate OUT=<dir> - validate manifest/schema + that every golden Q has a supporting doc (default: corpus/)"
	@echo "  stats OUT=<dir>    - print corpus composition (documents by format/type, golden by class)"
	@echo "  eval [PRED=<file>] - score predictions vs golden/ (Recall@K/nDCG/EM/F1); no PRED -> oracle self-check"
	@echo "  test               - run the generator test suite (determinism, etc.)"
	@echo "  clean              - remove generated corpus/ + caches"

# Full corpus. Rendering ~750 PDFs through WeasyPrint's native libraries can segfault at scale (#33):
# the first attempt runs clean; retries use --resume to keep already-rendered files and re-render only
# what's missing, so a native crash recovers cheaply and `make generate` reliably completes end-to-end.
generate:
	@for i in 1 2 3 4 5; do \
	  if [ $$i -eq 1 ]; then flag=; else flag=--resume; echo "[generate] retry $$i (resume — keeping rendered files)"; fi; \
	  if $(RUN) python -m generator.run --seed $(SEED) --out corpus --profile full $$flag; then exit 0; fi; \
	done; \
	echo "[generate] failed after 5 attempts"; exit 1

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

# Score a predictions file against the committed golden set. With no PRED, run the oracle
# self-check (a perfect run -> 1.0 on every metric except recall@1 for multi-doc questions).
GOLDEN ?= golden/golden.jsonl
eval:
ifdef PRED
	$(RUN) python -m generator.eval --golden $(GOLDEN) --predictions $(PRED)
else
	$(RUN) python -m generator.eval --golden $(GOLDEN) --oracle
endif

test:
	$(RUN) --extra dev pytest -q

clean:
	rm -rf corpus/ .cache/ .llm-cache/
