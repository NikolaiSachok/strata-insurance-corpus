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

import hashlib

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

# The visibly-damaged part/area in each scene — a purely VISUAL fact (readable only from the photo,
# stated on no text document), so it grounds a genuine `vision` golden question by construction. Kept
# deliberately distinct from the cause label (which the text docs DO state); a leak-guard test asserts
# each value is absent from every born-digital document's text.
_DAMAGE_AREA = {
    ("personal_auto", "rear_end_collision"): "rear bumper and boot",
    ("personal_auto", "single_vehicle"): "front end",
    ("personal_auto", "theft"): "side window and door lock",
    ("personal_auto", "hail"): "bonnet and roof",
    ("personal_auto", "vandalism"): "paintwork and a door panel",
    ("personal_auto", "animal_strike"): "front bumper and a headlight",
    ("homeowners", "water_damage"): "ceiling and a wall",
    ("homeowners", "kitchen_fire"): "kitchen cabinets",
    ("homeowners", "wind"): "roof",
    ("homeowners", "hail"): "roof tiles and gutters",
    ("homeowners", "theft"): "front door lock",
    ("homeowners", "liability_slip"): "hallway floor",
    ("bop", "fire"): "walls and stock",
    ("bop", "burglary"): "shop shutter",
    ("bop", "water_damage"): "storeroom floor and goods",
    ("bop", "slip_and_fall"): "shop entrance floor",
    ("bop", "business_interruption"): "shopfront",
    ("bop", "equipment_breakdown"): "an industrial machine",
}

# The corpus is synthetic-but-realistic: incidental product/vehicle branding, synthetic faces, and
# (invented) plates are fine — they are the realistic PII a redaction system is benchmarked on, and
# PII handling belongs in the consuming RAG layer, not the source documents. The only guardrails are
# against depicting a REAL identifiable individual or naming a REAL company as the claim party.
_NEGATIVE = (
    "no real, identifiable public figures or celebrities; any business or premises depicted is generic "
    "and fictional, not a real named chain or brand; storefronts, shopfronts, signs, and premises carry "
    "no legible business names, shop signage, brand logos, or readable lettering (blank, blurred, or "
    "illegible signage only); no text overlays or stock-photo watermarks. "
    "(synthetic vehicle number plates on cars may remain visible)"
)


def _image_seed(doc_id: str, corpus_seed: int) -> int:
    return corpus_seed * 100019 + sum(ord(c) for c in doc_id)


# Portrait guardrail: a fully synthetic, non-existent person (the realistic face PII a
# redaction system is benchmarked on) — never a likeness of a real, identifiable individual.
_FACE_NEGATIVE = (
    "not a real or identifiable person, not a celebrity or public figure, not a likeness of any "
    "existing individual; no text, no watermark, no document border"
)


# Deterministic appearance descriptors so each policyholder's synthetic portrait is a distinct
# person (the recipe stays reproducible — bucketed from the holder id via hashlib, not wall-clock/RNG).
# Gender is now a modelled attribute (#34), so the portrait uses `holder.gender` directly.
_FACE_AGES = ("a young {who}", "a {who} in their thirties", "a middle-aged {who}", "an older {who}")
_FACE_HAIR = ("with short hair", "with glasses", "with shoulder-length hair", "with greying hair",
              "with curly hair", "with straight dark hair", "with light hair", "with a shaved head",
              "with red hair", "with closely-cropped afro-textured hair")

# Even spread of ethnic appearance (#46), bucketed independently of gender/age/hair — realistic for a
# pan-European insurer AND enough samples per group (~8 of 80) to test vision/face-redaction bias.
# Written neutrally (skin tone + descent); the faces are fully synthetic, never a real individual.
_FACE_ETHNICITY = (
    "of Northern European descent with fair skin",
    "of Mediterranean European descent with olive skin",
    "of Eastern European / Slavic descent",
    "of Celtic descent with fair, freckled skin",
    "of North African / Maghrebi descent with light-brown skin",
    "of Sub-Saharan African descent with dark brown skin",
    "of Turkish or Middle-Eastern descent with olive skin",
    "of South Asian descent with brown skin",
    "of East Asian descent",
    "of mixed heritage",
)


def face_spec(holder: Policyholder, corpus_seed: int) -> dict:
    """Prompt spec for one policyholder's ID-portrait (deterministic, same tier as evidence).

    The pixels are non-deterministic AI output (rendered for the sample, recipe-only for the full
    set); this committed spec is the reproducible artifact. The face is embedded in that holder's
    identity card and is deliberately realistic — it is redaction-test material, not a real person.
    """
    country = COUNTRY_BY_CODE.get(holder.country)
    country_name = country.name if country else holder.country
    doc_id = f"DOC-{holder.id}-FACE"
    # Stable, well-distributed bucket (hashlib is independent of PYTHONHASHSEED; adjacent ids
    # that differ by one digit must not collide on the small age/hair moduli).
    h = int.from_bytes(hashlib.md5(holder.id.encode()).digest()[:4], "big")
    who = "man" if holder.gender == "male" else "woman"  # gender is modelled (#34) — no inference
    age = _FACE_AGES[h % len(_FACE_AGES)].format(who=who)
    hair = _FACE_HAIR[(h // len(_FACE_AGES)) % len(_FACE_HAIR)]
    ethnicity = _FACE_ETHNICITY[(h // (len(_FACE_AGES) * len(_FACE_HAIR))) % len(_FACE_ETHNICITY)]
    person = f"{age} {ethnicity}, {hair}"
    prompt = (
        f"A neutral passport-style identity portrait of a fictional {country_name} resident "
        f"({person}): head and shoulders, facing the camera, plain light-grey background, even studio "
        "lighting, neutral expression. Photorealistic but an entirely invented, non-existent person. "
        f"{_FACE_NEGATIVE}."
    )
    return {
        "doc_id": doc_id,
        "holder_id": holder.id,
        "country": holder.country,
        "kind": "id_portrait",
        "path": f"faces/{holder.id}-face.jpg",
        "model": MODEL,
        "params": {"aspect_ratio": "4:5", "resolution": "512", "seed": _image_seed(doc_id, corpus_seed)},
        "prompt": prompt,
        "negative_prompt": _FACE_NEGATIVE,
        "caption": f"Synthetic ID portrait for policyholder {holder.id} ({country_name}).",
    }


def evidence_spec(claim: Claim, policy: Policy, holder: Policyholder, corpus_seed: int) -> dict:
    """The prompt spec for one claim's evidence photo (deterministic)."""
    country = COUNTRY_BY_CODE.get(holder.country)
    country_name = country.name if country else holder.country
    scene = _SCENES.get((policy.line, claim.cause), f"insurance claim damage from {claim.cause.replace('_', ' ')}")
    damage_area = _DAMAGE_AREA.get((policy.line, claim.cause), "the damaged area")
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
        "damage_area": damage_area,  # by-construction label for the `vision` golden question
        "path": f"evidence/{claim.id}-evidence.jpg",
        "model": MODEL,
        "params": {"aspect_ratio": "4:3", "resolution": "1K", "seed": _image_seed(doc_id, corpus_seed)},
        "prompt": prompt,
        "negative_prompt": _NEGATIVE,
        "caption": f"{scene[0].upper()}{scene[1:]} — {LINE_LABEL[policy.line]} claim {claim.id} ({country_name}).",
    }
