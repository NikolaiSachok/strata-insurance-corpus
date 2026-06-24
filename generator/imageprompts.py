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
import importlib
from functools import lru_cache

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


# Portrait guardrail: a fully synthetic, non-existent person (the realistic face PII a
# redaction system is benchmarked on) — never a likeness of a real, identifiable individual.
_FACE_NEGATIVE = (
    "not a real or identifiable person, not a celebrity or public figure, not a likeness of any "
    "existing individual; no text, no watermark, no document border"
)


# Deterministic appearance descriptors so each policyholder's synthetic portrait is a distinct
# person (the recipe stays reproducible — derived from the holder id, not wall-clock/RNG). Gender
# is intentionally NOT asserted: policyholder gender is not a modelled attribute (see backlog),
# so a portrait's apparent gender is incidental and may not track the name's typical gender.
_FACE_AGES = ("a young {who}", "a {who} in their thirties", "a middle-aged {who}", "an older {who}")
_FACE_HAIR = ("with short hair", "with glasses", "with shoulder-length hair", "with greying hair",
              "with curly hair", "with straight dark hair", "with light hair", "with a shaved head")


@lru_cache(maxsize=None)
def _first_name_sets(locale: str) -> tuple[frozenset, frozenset]:
    """(male, female) first-name sets from Faker's provider data for a locale (membership only)."""
    try:
        provider = importlib.import_module(f"faker.providers.person.{locale}").Provider
    except Exception:  # pragma: no cover - locale always present for our 6 countries
        return frozenset(), frozenset()

    def names(attr: str) -> frozenset:
        v = getattr(provider, attr, None)
        if v is None:
            return frozenset()
        return frozenset(v.keys() if isinstance(v, dict) else v)

    return names("first_names_male"), names("first_names_female")


def _infer_gender(country_code: str, full_name: str) -> str | None:
    """Best-effort 'man'/'woman' from the given name via Faker's locale name lists, else None.

    Lets a synthetic portrait track the (Faker-generated) name's apparent gender WITHOUT making
    gender a modelled attribute — a pure, deterministic membership lookup, no RNG, no model change.
    """
    from .content import _strip_name
    from .identity import COUNTRY_BY_CODE as _CBC

    country = _CBC.get(country_code)
    if not country:
        return None
    parts = _strip_name(full_name).split()
    if not parts:
        return None
    given = parts[0]
    male, female = _first_name_sets(country.locale)
    in_m, in_f = given in male, given in female
    if in_m and not in_f:
        return "man"
    if in_f and not in_m:
        return "woman"
    return None  # unknown or ambiguous -> leave gender unspecified


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
    gender = _infer_gender(holder.country, holder.name)
    who = gender or "person"  # ID portrait should track the name's apparent gender where known
    age = _FACE_AGES[h % len(_FACE_AGES)].format(who=who)
    hair = _FACE_HAIR[(h // len(_FACE_AGES)) % len(_FACE_HAIR)]
    person = f"{age} {hair}"
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
