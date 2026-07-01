"""Golden evaluation set — by construction, grounded in provenance.

Because the model is known, answers are knowable; because each document records the
``(entity, field, value)`` facts it asserts (see ``provenance.py``), each golden answer is
**exactly what its cited documents state** and its relevant-doc set is **every document that
asserts the fact**. ``build_golden`` therefore resolves every question through the provenance
index rather than recomputing answers or hand-threading doc ids — a single source of truth.

Output format is aligned with general enterprise-RAG benchmarks:
``{id, question, answer, relevant_doc_ids, query_class, provenance}`` as JSONL.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .identity import COUNTRY_BY_CODE
from .model import Model
from .provenance import support_for


def _q(qid, question, value, doc_ids, query_class, entity_id, field, modality="text"):
    return {
        "id": qid,
        "question": question,
        "answer": value,
        "relevant_doc_ids": doc_ids,
        "query_class": query_class,
        "modality": modality,
        "provenance": {"entity_id": entity_id, "field": field},
    }


def _hop(prov, entity_id, field):
    """One step of a multi-hop chain: the asserted ``value`` + the docs that assert it, or ``None``."""
    support = support_for(prov, entity_id, field)
    if support is None:
        return None
    value, doc_ids = support
    return {"entity_id": entity_id, "field": field, "value": value, "doc_ids": doc_ids}


def _multihop(qid, question, hops, modality="text"):
    """A cross-document question: answer is the terminal hop's value; relevant docs span the whole chain."""
    relevant = sorted({d for h in hops for d in h["doc_ids"]})
    return {
        "id": qid,
        "question": question,
        "answer": hops[-1]["value"],
        "relevant_doc_ids": relevant,
        "query_class": "multi_hop",
        "modality": modality,
        "provenance": {"hops": hops},
    }


def build_golden(model: Model, prov: dict) -> list[dict]:
    """Build golden items, each grounded in the provenance index ``prov``.

    ``prov`` is ``provenance.provenance_index(records)`` — ``(entity_id, field) -> [(doc_id, value)]``.
    A question is emitted only when the fact is actually asserted by some document.
    """
    items: list[dict] = []

    def add(entity_id, field, qid, question, query_class, modality="text"):
        support = support_for(prov, entity_id, field)
        if support is None:
            return
        value, doc_ids = support
        items.append(_q(qid, question, value, doc_ids, query_class, entity_id, field, modality))

    # --- semantic / extractive -------------------------------------------- #
    for claim in model.claims:
        add(claim.id, "cause", f"Q-{claim.id}-cause",
            f"What cause of loss was recorded for claim {claim.id}?", "semantic")
        add(claim.id, "paid", f"Q-{claim.id}-settlement",
            f"What amount did Meridian Mutual pay to settle claim {claim.id}?", "semantic")
    for policy in model.policies:
        add(policy.id, "annual_premium", f"Q-{policy.id}-premium",
            f"What is the annual premium for policy {policy.id}?", "semantic")
        add(policy.id, "vehicle", f"Q-{policy.id}-vehicle",
            f"What make and model of vehicle is insured under policy {policy.id}?", "semantic")
    for holder in model.policyholders:
        country = COUNTRY_BY_CODE.get(holder.country)
        label = country.id_label if country else "national identifier"
        add(holder.id, "national_id", f"Q-{holder.id}-national-id",
            f"What is the {label} recorded for policyholder {holder.name} ({holder.id})?", "semantic")

    # --- aggregation / metadata (CORPUS-scoped facts asserted on the registers) -------- #
    add("CORPUS", "total_open_reserve", "Q-AGG-open-reserve",
        "What is the total open reserve across all claims?", "aggregation")
    add("CORPUS", "total_annual_premium", "Q-AGG-total-premium",
        "What is the total annual premium across all policies?", "aggregation")
    add("CORPUS", "open_claim_count", "Q-AGG-open-claims",
        "How many claims are currently open?", "aggregation")

    # --- knowledge-base semantic (fact stated in the guidelines) ----------- #
    add("CORPUS", "lines_of_business", "Q-KB-lines",
        "Which lines of business does Meridian Mutual underwrite?", "semantic")

    # --- multi-hop / cross-document --------------------------------------- #
    # The answer lives on a document you reach only by traversing from another: the FNOL ties a claim to
    # its policy (the bridge), but the policy's *premium* lives on the declarations and appears on no claim
    # document — so answering genuinely requires both hops. Each hop is grounded and relevant_doc_ids spans
    # the chain. We deliberately avoid "joins" whose answer fact already co-occurs with the bridge on one
    # document — e.g. the settlement letter states both the cause and the amount, and the FNOL already names
    # the insured vehicle — those are single-doc answerable, not multi-hop (enforced by a test).
    for claim in model.claims:
        bridge = _hop(prov, claim.id, "policy_id")  # claim -> policy (FNOL)
        if bridge is None:
            continue
        prem = _hop(prov, bridge["value"], "annual_premium")  # policy -> premium (declarations)
        if prem is not None:
            items.append(_multihop(
                f"Q-MH-{claim.id}-premium",
                f"What is the annual premium on the policy under which claim {claim.id} was filed?",
                [bridge, prem]))

    # --- multimodal (grounded on scan-only / image-only documents) -------- #
    # Each answer lives ONLY in a scanned or generated-image document (its born-digital text does not
    # exist / does not state it), so answering genuinely requires the modality — OCR, vision, or
    # image retrieval. The seeded prompt-spec / rendered scan is the by-construction label; a leak-guard
    # test asserts these answers appear on no born-digital page.
    claims_per_policy = Counter(c.policy_id for c in model.claims)  # for unambiguous cross-modal keying
    for claim in model.claims:
        # OCR — the police-report reference number, readable only off the scanned report.
        add(claim.id, "police_report_ref", f"Q-OCR-{claim.id}-police-ref",
            f"What is the police report reference number recorded for claim {claim.id}?",
            "semantic", modality="ocr")
        # Vision — the visibly-damaged area in the on-scene evidence photograph.
        add(claim.id, "evidence_damage", f"Q-VIS-{claim.id}-damage",
            f"In the on-scene evidence photograph for claim {claim.id}, which part or area is visibly damaged?",
            "semantic", modality="vision")
        # Cross-modal — join a claim document (text) to its evidence photo (image): find the claim
        # filed under a policy, then read the damage off the photo. The answer is on no text document.
        # Emitted ONLY when the policy has exactly ONE claim, so "the claim filed under policy P"
        # identifies the claim unambiguously (a multi-claim policy would give several rows the same
        # question text with conflicting answers). For multi-claim policies the per-claim `vision`
        # question already covers the photo.
        bridge = _hop(prov, claim.id, "policy_id")          # claim -> policy (FNOL, text bridge)
        dmg = _hop(prov, claim.id, "evidence_damage")       # claim -> damage (evidence photo, image)
        if bridge is not None and dmg is not None and claims_per_policy[bridge["value"]] == 1:
            items.append(_multihop(
                f"Q-XM-{claim.id}-photo-damage",
                f"What is visibly damaged in the on-scene evidence photograph for the claim filed under "
                f"policy {bridge['value']}?",
                [bridge, dmg], modality="cross_modal"))

    # Multimodal retrieval — retrieve a policyholder's on-file ID portrait (an image) by identity.
    for holder in model.policyholders:
        add(holder.id, "portrait", f"Q-MMR-{holder.id}-portrait",
            f"Retrieve the on-file identity portrait photograph of policyholder {holder.name} ({holder.id}).",
            "semantic", modality="multimodal_retrieval")

    items.sort(key=lambda x: x["id"])
    return items


def write_golden(outdir: Path, items: list[dict]) -> Path:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "golden.jsonl"
    lines = [json.dumps(it, sort_keys=True, ensure_ascii=False) for it in items]
    path.write_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
    return path
