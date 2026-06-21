# strata-insurance-corpus — build targets (STUB; implemented per the M1–M5 roadmap in BRIEF.md)
SEED ?= 42

.PHONY: help generate sample validate clean

help:
	@echo "Targets (see BRIEF.md):"
	@echo "  generate SEED=<n>  - deterministically generate the full corpus + manifest + golden eval"
	@echo "  sample             - regenerate the small committed sample/ slice"
	@echo "  validate           - validate manifest/schema + that every golden Q has a supporting doc"
	@echo "  clean              - remove generated corpus/ + caches"

generate:
	@echo "TODO (M1+): python -m generator.run --seed $(SEED) --out corpus/"

sample:
	@echo "TODO (M2): python -m generator.run --seed $(SEED) --profile sample --out sample/"

validate:
	@echo "TODO (M4): python -m generator.validate --corpus corpus/ --golden golden/golden.jsonl"

clean:
	rm -rf corpus/ .cache/ .llm-cache/
