"""Golden evaluation set — by construction.

Because the model is known, answers are knowable. M1 emits the semantic /
extractive class: each FNOL supports a "what cause of loss" question whose answer
is the recorded cause label and whose supporting doc is that FNOL. Aggregation
and multi-hop classes arrive in M4 (issues #13–#15).

Output format is aligned with general enterprise-RAG benchmarks:
``{id, question, answer, relevant_doc_ids, query_class, provenance}`` as JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path

from .content import cause_label
from .model import Model


def build_golden(
    model: Model,
    fnol_doc_for_claim: dict,
    decl_doc_for_policy: dict | None = None,
    settlement_doc_for_claim: dict | None = None,
) -> list[dict]:
    """Build golden items (semantic class).

    ``fnol_doc_for_claim`` maps claim_id -> FNOL doc_id (cause questions);
    ``decl_doc_for_policy`` maps policy_id -> declarations doc_id (premium questions);
    ``settlement_doc_for_claim`` maps claim_id -> settlement-letter doc_id (paid-amount questions).
    """
    decl_doc_for_policy = decl_doc_for_policy or {}
    settlement_doc_for_claim = settlement_doc_for_claim or {}
    items: list[dict] = []
    for claim in model.claims:
        doc_id = fnol_doc_for_claim.get(claim.id)
        if not doc_id:
            continue
        items.append(
            {
                "id": f"Q-{claim.id}-cause",
                "question": f"What cause of loss was recorded for claim {claim.id}?",
                "answer": cause_label(claim.cause),
                "relevant_doc_ids": [doc_id],
                "query_class": "semantic",
                "provenance": {"entity_id": claim.id, "field": "cause"},
            }
        )
    for policy in model.policies:
        doc_id = decl_doc_for_policy.get(policy.id)
        if not doc_id:
            continue
        items.append(
            {
                "id": f"Q-{policy.id}-premium",
                "question": f"What is the annual premium for policy {policy.id}?",
                "answer": f"${policy.annual_premium:,.2f}",
                "relevant_doc_ids": [doc_id],
                "query_class": "semantic",
                "provenance": {"entity_id": policy.id, "field": "annual_premium"},
            }
        )
    for claim in model.claims:
        doc_id = settlement_doc_for_claim.get(claim.id)
        if not doc_id:
            continue
        items.append(
            {
                "id": f"Q-{claim.id}-settlement",
                "question": f"What amount did Meridian Mutual pay to settle claim {claim.id}?",
                "answer": f"${claim.paid:,.2f}",
                "relevant_doc_ids": [doc_id],
                "query_class": "semantic",
                "provenance": {"entity_id": claim.id, "field": "paid"},
            }
        )
    items.sort(key=lambda x: x["id"])
    return items


def write_golden(outdir: Path, items: list[dict]) -> Path:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "golden.jsonl"
    lines = [json.dumps(it, sort_keys=True, ensure_ascii=False) for it in items]
    path.write_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
    return path
