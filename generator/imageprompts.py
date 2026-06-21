"""Deterministic evidence-image **prompt specs** (issue #11).

AI-generated image *pixels* cannot be byte-deterministic, so the corpus's committed,
reproducible artifact is the **prompt spec** — the exact prompt + model + settings used
to render each evidence photo — emitted as ``image-prompts.jsonl``. The pixels are a
separate, non-deterministic tier (rendered for the ``sample/`` slice; the full set is
produced on-demand for the HuggingFace release). Each spec is derived from the claim's
cause/line/country, so the recipe is knowable and stable.

Mirrors how LLM prose is cached by ``(seed, doc_id)``: the instructions reproduce even
where the output isn't bit-exact.
"""

from __future__ import annotations

from .identity import COUNTRY_BY_CODE
from .model import LINE_LABEL, Claim, Policyholder, Policy

MODEL = "gemini-3.1-flash-image"  # Nano Banana 2 (Flash) — photoreal, no text to mangle

# Per-(line, cause) scene description. Causes are defined in model.CAUSES.
_SCENES = {
    ("personal_auto", "rear_end_collision"): "a car with rear-end collision damage — crumpled rear bumper and dented boot",
    ("personal_auto", "single_vehicle"): "a car with front-end damage after a single-vehicle accident",
    ("personal_auto", "theft"): "a car with a smashed side window and damaged door lock after a break-in",
    ("personal_auto", "hail"): "a car bonnet and roof covered in small round hail dents",
    ("personal_auto", "vandalism"): "a car with scratched paintwork and a keyed door panel",
    ("personal_auto", "animal_strike"): "a car with front bumper and headlight damage after an animal strike",
    ("homeowners", "water_damage"): "interior water damage to a home — a stained, sagging ceiling and damp wall",
    ("homeowners", "kitchen_fire"): "fire and smoke damage in a domestic kitchen — charred cabinets and soot",
    ("homeowners", "wind"): "storm wind damage to a house roof — dislodged tiles and scattered debris",
    ("homeowners", "hail"): "hail damage to a home's roof tiles and gutters",
    ("homeowners", "theft"): "a forced-open residential door with a damaged lock after a burglary",
    ("homeowners", "liability_slip"): "a wet tiled hallway floor with a caution sign where a slip occurred",
    ("bop", "fire"): "fire damage inside small commercial premises — charred walls and stock",
    ("bop", "burglary"): "a forced-open shop shutter and a ransacked retail interior after a burglary",
    ("bop", "water_damage"): "water damage in a small-business storeroom — a flooded floor and damaged goods",
    ("bop", "slip_and_fall"): "a wet floor in a shop entrance marked with a hazard cone",
    ("bop", "business_interruption"): "a closed small business with shutters down and a temporary-closure notice",
    ("bop", "equipment_breakdown"): "a broken-down industrial machine in a workshop with a visible fault",
}
_KIND = {"personal_auto": "vehicle_damage", "homeowners": "property_damage", "bop": "commercial_damage"}

# The corpus is synthetic-but-realistic: incidental product/vehicle branding, synthetic faces, and
# (invented) plates are fine — they are the realistic PII a redaction system is benchmarked on, and
# PII handling belongs in the consuming RAG layer, not the source documents. The only guardrails are
# against depicting a REAL identifiable individual or naming a REAL company as the claim party.
_NEGATIVE = (
    "no real, identifiable public figures or celebrities; any business or premises depicted is generic "
    "and fictional, not a real named chain or brand; no text overlays or stock-photo watermarks"
)


def _image_seed(doc_id: str, corpus_seed: int) -> int:
    return corpus_seed * 100019 + sum(ord(c) for c in doc_id)


def evidence_spec(claim: Claim, policy: Policy, holder: Policyholder, corpus_seed: int) -> dict:
    """The prompt spec for one claim's evidence photo (deterministic)."""
    country = COUNTRY_BY_CODE.get(holder.country)
    country_name = country.name if country else holder.country
    scene = _SCENES.get((policy.line, claim.cause), f"insurance claim damage from {claim.cause.replace('_', ' ')}")
    doc_id = f"DOC-{claim.id}-EVIDENCE"
    prompt = (
        f"A candid amateur smartphone photo submitted as insurance claim evidence in {country_name}: "
        f"{scene}. Natural daylight, slightly imperfect amateur phone-camera framing, realistic and "
        f"true-to-life. {_NEGATIVE}."
    )
    return {
        "doc_id": doc_id,
        "claim_id": claim.id,
        "line": policy.line,
        "cause": claim.cause,
        "country": holder.country,
        "kind": _KIND[policy.line],
        "path": f"evidence/{claim.id}-evidence.jpg",
        "model": MODEL,
        "params": {"aspect_ratio": "4:3", "resolution": "1K", "seed": _image_seed(doc_id, corpus_seed)},
        "prompt": prompt,
        "negative_prompt": _NEGATIVE,
        "caption": f"{scene[0].upper()}{scene[1:]} — {LINE_LABEL[policy.line]} claim {claim.id} ({country_name}).",
    }
