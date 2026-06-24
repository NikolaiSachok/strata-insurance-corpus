"""Redaction ground-truth index (issue #12).

The corpus deliberately contains realistic **synthetic PII** — names, addresses, dates of
birth, phone/email, national identifiers, vehicle plates, ID-card numbers + machine-readable
zones, and synthetic faces. PII *handling* (detection/redaction) is the job of the consuming
RAG layer, **not** the source corpus — so rather than strip or mask anything, we publish a
**machine-readable catalogue of every PII span**: for each document, which entity it belongs to,
its type, the source field, and the exact surface value to redact. A redaction/PII-detection
system can then be **scored** (precision/recall) against this known ground truth.

Design:
  * The index is a **pure, deterministic function of the model** (not of the rendered pixels or a
    PDF text layer), so it is byte-stable and decoupled from render-library versions.
  * Accuracy is enforced separately: a test extracts the rendered text of every committed sample
    document and asserts each catalogued text span actually appears (drift guard).
  * Scanned variants inherit their source document's spans with ``modality: image_text`` (the same
    PII, now an OCR+redaction target). The ID portrait is an ``image_region`` FACE span.

Span shape (one JSON object per line in ``pii-index.jsonl``)::

    {"doc_id", "doc_type", "is_scanned", "modality",
     "entity_id", "entity_type", "pii_type", "field", "value"}
"""

from __future__ import annotations

from .content import _eu_date, accident_statement_document, id_card_document
from .model import Model, index

# PII taxonomy (aligned with common PII/PHI detector label sets).
PERSON_NAME = "PERSON_NAME"
ADDRESS = "ADDRESS"
DATE_OF_BIRTH = "DATE_OF_BIRTH"
EMAIL_ADDRESS = "EMAIL_ADDRESS"
PHONE_NUMBER = "PHONE_NUMBER"
NATIONAL_ID = "NATIONAL_ID"
POLICY_NUMBER = "POLICY_NUMBER"
CLAIM_NUMBER = "CLAIM_NUMBER"
VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
ID_DOCUMENT_NUMBER = "ID_DOCUMENT_NUMBER"
MRZ = "MRZ"
FACE = "FACE"

_ROLE_PREFIX = {"holder": "PH-", "agent": "AG-", "adjuster": "AD-", "claim": "C-"}
_POLICY_PREFIXES = ("MOT-", "HH-", "COM-")

# Per-doc-type render profile: which PII categories each role's entity contributes. Kept accurate
# by the text-grounding test (every catalogued text span must appear in the rendered document).
_NAME, _ADDR, _POL, _CLM, _VEH, _CONTACT, _CITY = "NAME", "ADDRESS", "POLICY", "CLAIM", "VEHICLE", "CONTACT", "CITY"
DOC_PII_PROFILE: dict[str, dict[str, list[str]]] = {
    "policy_declarations": {"holder": [_NAME, _ADDR], "agent": [_NAME], "policy": [_POL, _VEH]},
    "policy_contract": {"holder": [_NAME], "policy": [_POL]},
    "policy_endorsements": {"holder": [_NAME], "policy": [_POL]},
    "policy_schedule": {"holder": [_NAME], "policy": [_POL]},
    "fnol": {"holder": [_NAME, _CONTACT], "adjuster": [_NAME], "policy": [_POL, _VEH], "claim": [_CLM]},
    "adjuster_report": {"holder": [_NAME], "adjuster": [_NAME], "policy": [_POL], "claim": [_CLM]},
    "estimate": {"holder": [_NAME], "policy": [_POL], "claim": [_CLM]},
    "settlement_letter": {"holder": [_NAME, _ADDR], "adjuster": [_NAME], "policy": [_POL], "claim": [_CLM]},
    "denial_letter": {"holder": [_NAME, _ADDR], "adjuster": [_NAME], "policy": [_POL], "claim": [_CLM]},
    "accident_statement": {"holder": [_NAME, _CITY], "policy": [_POL, _VEH], "claim": [_CLM]},
}
_REGISTER_TYPES = {"loss_run", "reserve_register", "premium_register", "commission_summary"}
_NO_PII_TYPES = {"underwriting_guidelines", "claims_manual", "customer_faq", "evidence_photo"}


def _span(doc, entity_id, entity_type, pii_type, field, value, modality="text"):
    return {
        "doc_id": doc.doc_id,
        "doc_type": doc.doc_type,
        "is_scanned": bool(doc.is_scanned),
        "modality": modality,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "pii_type": pii_type,
        "field": field,
        "value": value,
    }


def _find(entity_ids, role):
    pref = _ROLE_PREFIX.get(role)
    if pref:
        return next((e for e in entity_ids if e.startswith(pref)), None)
    if role == "policy":
        return next((e for e in entity_ids if e.startswith(_POLICY_PREFIXES)), None)
    return None


def _holder_spans(doc, holder, cats):
    out = []
    if _NAME in cats:
        out.append(_span(doc, holder.id, "policyholder", PERSON_NAME, "name", holder.name))
    if _ADDR in cats:
        out.append(_span(doc, holder.id, "policyholder", ADDRESS, "street", holder.street))
        out.append(_span(doc, holder.id, "policyholder", ADDRESS, "city", holder.city))
        out.append(_span(doc, holder.id, "policyholder", ADDRESS, "postcode", holder.postcode))
    elif _CITY in cats:  # only the city is rendered (e.g. accident-statement location)
        out.append(_span(doc, holder.id, "policyholder", ADDRESS, "city", holder.city))
    if _CONTACT in cats:
        out.append(_span(doc, holder.id, "policyholder", PHONE_NUMBER, "phone", holder.phone))
        out.append(_span(doc, holder.id, "policyholder", EMAIL_ADDRESS, "email", holder.email))
    return out


def _id_card_spans(doc, model_meta, holder):
    """Full PII surface of an identity card — names + DOB + address + national id + card no + MRZ."""
    vm = id_card_document(model_meta, holder, None)
    out = [
        _span(doc, holder.id, "policyholder", PERSON_NAME, "name", f"{vm['given_names']} {vm['surname']}".strip()),
        _span(doc, holder.id, "policyholder", DATE_OF_BIRTH, "dob", vm["dob"]),
        _span(doc, holder.id, "policyholder", ADDRESS, "street", holder.street),
        _span(doc, holder.id, "policyholder", ADDRESS, "city", holder.city),
        _span(doc, holder.id, "policyholder", ADDRESS, "postcode", holder.postcode),
        _span(doc, holder.id, "policyholder", NATIONAL_ID, "national_id", holder.national_id),
        _span(doc, holder.id, "policyholder", ID_DOCUMENT_NUMBER, "card_no", vm["card_no"]),
    ]
    for i, line in enumerate(vm["mrz"]):
        out.append(_span(doc, holder.id, "policyholder", MRZ, f"mrz_line_{i + 1}", line))
    return out


def _other_party_spans(doc, model_meta, claim, policy, holder):
    """The synthetic 'other party' on a collision accident statement (doc-local PII — a third
    party's name + plate, not a Meridian entity, so scoped to the claim)."""
    vm = accident_statement_document(model_meta, claim, policy, holder)
    other = vm.get("vehicle_b")
    if not other:
        return []
    return [
        _span(doc, claim.id, "third_party", PERSON_NAME, "other_driver", other["driver"]),
        _span(doc, claim.id, "third_party", VEHICLE_REGISTRATION, "other_plate", other["plate"]),
    ]


def _register_spans(doc, model):
    """PII rows for the tabular registers (corpus-level docs that list ids/names verbatim)."""
    out = []
    t = doc.doc_type
    if t == "loss_run":
        for c in model.claims:
            out.append(_span(doc, c.id, "claim", CLAIM_NUMBER, "id", c.id))
            out.append(_span(doc, c.policy_id, "policy", POLICY_NUMBER, "policy_id", c.policy_id))
    elif t == "reserve_register":
        for c in [c for c in model.claims if c.status == "open"]:
            out.append(_span(doc, c.id, "claim", CLAIM_NUMBER, "id", c.id))
            out.append(_span(doc, c.policy_id, "policy", POLICY_NUMBER, "policy_id", c.policy_id))
    elif t == "premium_register":
        idx = index(model)
        for p in model.policies:
            out.append(_span(doc, p.id, "policy", POLICY_NUMBER, "id", p.id))
            holder = idx["policyholders"].get(p.holder_id)
            if holder:
                out.append(_span(doc, holder.id, "policyholder", PERSON_NAME, "name", holder.name))
    elif t == "commission_summary":
        for a in model.agents:
            out.append(_span(doc, a.id, "agent", PERSON_NAME, "name", a.name))
    return out


def build_pii_index(model: Model, records: list) -> list[dict]:
    """Deterministic redaction ground-truth: every PII span in every document."""
    idx = index(model)
    by_doc: dict[str, list[dict]] = {}
    scanned: list = []

    for doc in records:
        if doc.is_scanned:
            scanned.append(doc)
            continue
        spans: list[dict] = []
        t = doc.doc_type
        if t == "id_card":
            holder = idx["policyholders"].get(_find(doc.entity_ids, "holder"))
            if holder:
                spans = _id_card_spans(doc, model.meta, holder)
        elif t == "id_photo":
            holder_id = _find(doc.entity_ids, "holder")
            if holder_id:
                spans = [_span(doc, holder_id, "policyholder", FACE, "portrait", None, modality="image_region")]
        elif t in _REGISTER_TYPES:
            spans = _register_spans(doc, model)
        elif t in DOC_PII_PROFILE:
            for role, cats in DOC_PII_PROFILE[t].items():
                eid = _find(doc.entity_ids, role)
                if not eid:
                    continue
                if role == "holder":
                    spans += _holder_spans(doc, idx["policyholders"][eid], cats)
                elif role in ("agent", "adjuster"):
                    ent = idx["agents" if role == "agent" else "adjusters"][eid]
                    spans.append(_span(doc, eid, role, PERSON_NAME, "name", ent.name))
                elif role == "policy":
                    if _POL in cats:
                        spans.append(_span(doc, eid, "policy", POLICY_NUMBER, "id", eid))
                    if _VEH in cats:
                        veh = idx["policies"][eid].vehicle
                        if veh and veh.get("registration"):
                            spans.append(_span(doc, eid, "policy", VEHICLE_REGISTRATION, "registration", veh["registration"]))
                elif role == "claim":
                    spans.append(_span(doc, eid, "claim", CLAIM_NUMBER, "id", eid))
            if t == "accident_statement":
                cid = _find(doc.entity_ids, "claim")
                claim = idx["claims"].get(cid) if cid else None
                if claim:
                    policy = idx["policies"][claim.policy_id]
                    holder = idx["policyholders"][claim.holder_id]
                    spans += _other_party_spans(doc, model.meta, claim, policy, holder)
        # _NO_PII_TYPES and anything unrecognised -> no spans
        by_doc[doc.doc_id] = spans

    all_spans = [s for doc in records if not doc.is_scanned for s in by_doc.get(doc.doc_id, [])]

    # Scanned variants inherit their source document's spans as image-text redaction targets.
    for doc in scanned:
        for src in by_doc.get(doc.source_doc_id, []):
            s = dict(src)
            s.update({"doc_id": doc.doc_id, "doc_type": doc.doc_type, "is_scanned": True, "modality": "image_text"})
            all_spans.append(s)

    all_spans.sort(key=lambda s: (s["doc_id"], s["pii_type"], s["field"], s["entity_id"], str(s["value"])))
    return all_spans


def write_pii_index(out, spans: list[dict]):
    """Write the deterministic PII ground-truth index as JSONL (sorted, UTF-8)."""
    import json
    from pathlib import Path

    path = Path(out) / "pii-index.jsonl"
    lines = [json.dumps(s, sort_keys=True, ensure_ascii=False) for s in spans]
    path.write_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
    return path
