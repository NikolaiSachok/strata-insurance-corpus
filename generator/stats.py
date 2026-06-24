"""Print the composition of a generated corpus (the scale-run summary).

    python -m generator.stats --out corpus/

Reads ``manifest.json`` + ``golden.jsonl`` and prints entity counts, documents by
format and by doc-type, and golden questions by query class. Read-only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _row(label: str, n: int) -> str:
    return f"  {label:<26}{n:>6}"


def summarize(out: Path) -> dict:
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    counts = manifest.get("counts", {})

    golden_path = out / "golden.jsonl"
    by_class: Counter = Counter()
    n_golden = 0
    if golden_path.exists():
        for raw in golden_path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                n_golden += 1
                by_class[json.loads(raw).get("query_class", "?")] += 1

    pii_path = out / "pii-index.jsonl"
    by_pii: Counter = Counter()
    n_pii = 0
    if pii_path.exists():
        for raw in pii_path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                n_pii += 1
                by_pii[json.loads(raw).get("pii_type", "?")] += 1

    return {
        "pii_spans": n_pii,
        "pii_by_type": dict(sorted(by_pii.items())),
        "out": str(out),
        "seed": manifest.get("seed"),
        "profile": manifest.get("profile"),
        "entities": {k: counts[k] for k in ("policyholders", "agents", "adjusters", "policies", "claims") if k in counts},
        "documents": counts.get("documents", 0),
        "by_format": counts.get("by_format", {}),
        "by_doc_type": counts.get("by_doc_type", {}),
        "golden": n_golden,
        "golden_by_class": dict(sorted(by_class.items())),
    }


def render(s: dict) -> str:
    lines = [
        f"Corpus: {s['out']}  (seed={s['seed']}, profile={s['profile']})",
        "",
        "Entities:",
        *[_row(k, v) for k, v in s["entities"].items()],
        "",
        f"Documents: {s['documents']}",
        "  by format:",
        *[_row("  " + k, v) for k, v in s["by_format"].items()],
        "  by type:",
        *[_row("  " + k, v) for k, v in s["by_doc_type"].items()],
        "",
        f"Golden questions: {s['golden']}",
        *[_row("  " + k, v) for k, v in s["golden_by_class"].items()],
        "",
        f"PII spans (redaction ground truth): {s['pii_spans']}",
        *[_row("  " + k, v) for k, v in s["pii_by_type"].items()],
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="generator.stats")
    ap.add_argument("--out", type=Path, default=Path("corpus"))
    args = ap.parse_args(argv)
    if not (args.out / "manifest.json").exists():
        print(f"[stats] no manifest at {args.out} — run `make generate` or `make sample` first")
        return 1
    print(render(summarize(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
