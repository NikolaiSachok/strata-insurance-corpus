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

from . import tabular
from .content import cause_label
from .model import LINE_LABEL, LINES, Model


def build_golden(
    model: Model,
    fnol_doc_for_claim: dict,
    decl_doc_for_policy: dict | None = None,
    settlement_doc_for_claim: dict | None = None,
    tabular_doc_ids: dict | None = None,
    kb_doc_ids: dict | None = None,
) -> list[dict]:
    """Build golden items.

    Semantic class: ``fnol_doc_for_claim`` (cause), ``decl_doc_for_policy`` (premium),
    ``settlement_doc_for_claim`` (settlement amount). Aggregation class:
    ``tabular_doc_ids`` maps a tabular doc_type -> doc_id (totals/counts computed from the model).
    """
    decl_doc_for_policy = decl_doc_for_policy or {}
    settlement_doc_for_claim = settlement_doc_for_claim or {}
    tabular_doc_ids = tabular_doc_ids or {}
    kb_doc_ids = kb_doc_ids or {}
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
    # Aggregation class — answers computed from the model (the tabular docs are the retrieval target).
    if tabular_doc_ids.get("reserve_register"):
        items.append(
            {
                "id": "Q-AGG-open-reserve",
                "question": "What is the total open reserve across all claims?",
                "answer": f"${tabular.total_open_reserve(model):,.2f}",
                "relevant_doc_ids": [tabular_doc_ids["reserve_register"]],
                "query_class": "aggregation",
                "provenance": {"entity_id": "CORPUS", "field": "sum(reserve) where status=open"},
            }
        )
    if tabular_doc_ids.get("premium_register"):
        items.append(
            {
                "id": "Q-AGG-total-premium",
                "question": "What is the total annual premium across all policies?",
                "answer": f"${tabular.total_annual_premium(model):,.2f}",
                "relevant_doc_ids": [tabular_doc_ids["premium_register"]],
                "query_class": "aggregation",
                "provenance": {"entity_id": "CORPUS", "field": "sum(annual_premium)"},
            }
        )
    if tabular_doc_ids.get("loss_run"):
        items.append(
            {
                "id": "Q-AGG-open-claims",
                "question": "How many claims are currently open?",
                "answer": str(tabular.open_claim_count(model)),
                "relevant_doc_ids": [tabular_doc_ids["loss_run"]],
                "query_class": "aggregation",
                "provenance": {"entity_id": "CORPUS", "field": "count(claims) where status=open"},
            }
        )
    # Knowledge-base semantic question (answer is a model-grounded fact stated in the KB).
    if kb_doc_ids.get("underwriting_guidelines"):
        items.append(
            {
                "id": "Q-KB-lines",
                "question": "Which lines of business does Meridian Mutual underwrite?",
                "answer": ", ".join(LINE_LABEL[ln] for ln in LINES),
                "relevant_doc_ids": [kb_doc_ids["underwriting_guidelines"]],
                "query_class": "semantic",
                "provenance": {"entity_id": "CORPUS", "field": "lines_of_business"},
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
