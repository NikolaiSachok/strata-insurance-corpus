"""Reference eval harness (#15) — score predictions against the golden set.

A small, self-contained scorer so the corpus is usable **standalone with any RAG stack**: feed it a
predictions file and it reports retrieval and answer metrics against ``golden.jsonl``, broken down by
query class. (The full RAG engine is [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG); the M5
adapter lets it mount this corpus and use its own metrics. This harness is the dependency-free reference.)

Predictions file — JSONL, one object per answered question::

    {"id": "Q-C-1000-cause", "retrieved_doc_ids": ["DOC-C-1000-FNOL", "DOC-C-1000-ADJ", ...], "answer": "burglary"}

``retrieved_doc_ids`` is the system's ranked retrieval (best first); ``answer`` is its generated answer.
A golden question with no prediction scores 0 on every metric (so coverage gaps count against the system);
``n_with_prediction`` reports how many were answered.

Metrics (binary relevance, macro-averaged over questions):
  * **Recall@K** — fraction of the relevant docs found in the top-K.
  * **nDCG@K** — rank-weighted retrieval quality.
  * **exact_match** — normalized exact answer match.
  * **token_f1** — token-overlap F1 (partial credit).

    python -m generator.eval --golden golden/golden.jsonl --predictions preds.jsonl
    python -m generator.eval --golden sample/golden.jsonl --oracle   # self-check: perfect run -> 1.0
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

_WS = re.compile(r"\s+")


def normalize(s) -> str:
    """Lowercase, collapse whitespace, strip — used for answer matching."""
    return _WS.sub(" ", str(s).strip().lower())


def recall_at_k(relevant, retrieved: list, k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    return len(rel & set(retrieved[:k])) / len(rel)


def ndcg_at_k(relevant, retrieved: list, k: int) -> float:
    rel = set(relevant)
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(retrieved[:k]) if d in rel)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal if ideal else 0.0


def exact_match(pred, gold) -> float:
    return 1.0 if normalize(pred) == normalize(gold) else 0.0


def token_f1(pred, gold) -> float:
    p, g = normalize(pred).split(), normalize(gold).split()
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    overlap = sum((Counter(p) & Counter(g)).values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(g)
    return 2 * precision * recall / (precision + recall)


def _per_question(q: dict, pred: dict, ks) -> dict:
    retrieved = pred.get("retrieved_doc_ids", [])
    answer = pred.get("answer", "")
    rel = q["relevant_doc_ids"]
    m = {f"recall@{k}": recall_at_k(rel, retrieved, k) for k in ks}
    m[f"ndcg@{max(ks)}"] = ndcg_at_k(rel, retrieved, max(ks))
    m["exact_match"] = exact_match(answer, q["answer"])
    m["token_f1"] = token_f1(answer, q["answer"])
    return m


def _aggregate(metric_rows: list) -> dict:
    keys = list(metric_rows[0].keys())
    return {k: round(sum(r[k] for r in metric_rows) / len(metric_rows), 4) for k in keys}


def evaluate(golden: list, predictions: dict, ks=(1, 5, 10)) -> dict:
    """Score ``predictions`` (id -> {retrieved_doc_ids, answer}) against ``golden``."""
    rows, by_class, answered = [], defaultdict(list), 0
    for q in golden:
        pred = predictions.get(q["id"], {})
        if q["id"] in predictions:
            answered += 1
        m = _per_question(q, pred, ks)
        rows.append(m)
        by_class[q["query_class"]].append(m)
    return {
        "n_questions": len(golden),
        "n_with_prediction": answered,
        "k_values": list(ks),
        "overall": _aggregate(rows) if rows else {},
        "by_class": {c: _aggregate(ms) for c, ms in sorted(by_class.items())},
    }


def format_report(metrics: dict) -> str:
    overall = metrics["overall"]
    cols = list(overall.keys())
    lines = [
        f"Eval — {metrics['n_with_prediction']}/{metrics['n_questions']} questions answered "
        f"(K={metrics['k_values']})",
        "",
        "  " + f"{'class':<14}" + "".join(f"{c:>13}" for c in cols),
        "  " + "-" * (14 + 13 * len(cols)),
    ]
    for cls, m in metrics["by_class"].items():
        lines.append("  " + f"{cls:<14}" + "".join(f"{m[c]:>13.4f}" for c in cols))
    lines.append("  " + f"{'OVERALL':<14}" + "".join(f"{overall[c]:>13.4f}" for c in cols))
    return "\n".join(lines)


def load_golden(path: Path) -> list:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_predictions(path: Path) -> dict:
    preds = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            preds[p["id"]] = p
    return preds


def oracle_predictions(golden: list) -> dict:
    """A perfect run (relevant docs retrieved, gold answer) — a self-check that metrics hit 1.0."""
    return {q["id"]: {"retrieved_doc_ids": list(q["relevant_doc_ids"]), "answer": q["answer"]} for q in golden}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="generator.eval", description="Score predictions against the golden set.")
    ap.add_argument("--golden", type=Path, default=Path("golden/golden.jsonl"))
    ap.add_argument("--predictions", type=Path, help="JSONL: {id, retrieved_doc_ids, answer} per question")
    ap.add_argument("--oracle", action="store_true", help="score a perfect run (sanity check -> 1.0)")
    ap.add_argument("--k", type=int, nargs="+", default=[1, 5, 10], help="K values for Recall@K / nDCG@K")
    ap.add_argument("--out", type=Path, help="write the full metrics JSON here")
    args = ap.parse_args(argv)

    golden = load_golden(args.golden)
    if args.oracle:
        predictions = oracle_predictions(golden)
    elif args.predictions:
        predictions = load_predictions(args.predictions)
    else:
        ap.error("provide --predictions <file> or --oracle")

    metrics = evaluate(golden, predictions, ks=tuple(args.k))
    print(format_report(metrics))
    if args.out:
        Path(args.out).write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\n[eval] metrics -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
