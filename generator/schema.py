"""JSON Schema for the entity model + the roster TSV column contract.

Emitted to ``<out>/schema/`` so consumers (and CI) can validate ``model.json``
and ``roster.tsv`` against a stable contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import LINES, ROSTER_COLUMNS, STATUSES

_STR = {"type": "string"}
_NUM = {"type": "number"}


def _obj(props: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": props,
    }


MODEL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/NikolaiSachok/strata-insurance-corpus/schema/model.schema.json",
    "title": "Meridian Mutual entity model",
    "type": "object",
    "additionalProperties": False,
    "required": ["meta", "policyholders", "agents", "adjusters", "policies", "claims"],
    "properties": {
        "meta": _obj(
            {
                "company": _STR,
                "marker": _STR,
                "synthetic": {"const": True},
                "generator_version": _STR,
                "seed": {"type": "integer"},
                "profile": _STR,
                "anchor_date": {"type": "string", "format": "date"},
                "counts": {"type": "object"},
            },
            ["company", "marker", "synthetic", "seed", "profile"],
        ),
        "policyholders": {
            "type": "array",
            "items": _obj(
                {
                    "id": {"type": "string", "pattern": "^PH-[0-9]{5}$"},
                    "name": _STR,
                    "gender": {"enum": ["male", "female"]},
                    "dob": {"type": "string", "format": "date"},
                    "email": _STR,
                    "phone": _STR,
                    "street": _STR,
                    "city": _STR,
                    "postcode": _STR,
                    "country": {"enum": ["DE", "FR", "ES", "IT", "NL", "IE"]},
                    "national_id": _STR,  # synthetic, format-shaped but deliberately invalid (see identity.py)
                },
                ["id", "name", "gender", "dob", "country", "national_id"],
            ),
        },
        "agents": {
            "type": "array",
            "items": _obj(
                {"id": {"type": "string", "pattern": "^AG-[0-9]{3}$"}, "name": _STR, "agency": _STR, "region": _STR},
                ["id", "name"],
            ),
        },
        "adjusters": {
            "type": "array",
            "items": _obj(
                {"id": {"type": "string", "pattern": "^AD-[0-9]{3}$"}, "name": _STR, "specialty": _STR},
                ["id", "name"],
            ),
        },
        "policies": {
            "type": "array",
            "items": _obj(
                {
                    "id": _STR,
                    "holder_id": {"type": "string", "pattern": "^PH-[0-9]{5}$"},
                    "agent_id": {"type": "string", "pattern": "^AG-[0-9]{3}$"},
                    "line": {"enum": list(LINES)},
                    "effective_date": {"type": "string", "format": "date"},
                    "expiry_date": {"type": "string", "format": "date"},
                    "annual_premium": _NUM,
                    "limits": {"type": "object"},
                    "deductible": _NUM,
                    "endorsements": {"type": "array", "items": _STR},
                    "vehicle": {"type": ["object", "null"]},  # insured vehicle (Motor only)
                },
                ["id", "holder_id", "agent_id", "line", "effective_date", "expiry_date", "annual_premium"],
            ),
        },
        "claims": {
            "type": "array",
            "items": _obj(
                {
                    "id": {"type": "string", "pattern": "^C-[0-9]+$"},
                    "policy_id": _STR,
                    "holder_id": {"type": "string", "pattern": "^PH-[0-9]{5}$"},
                    "adjuster_id": {"type": "string", "pattern": "^AD-[0-9]{3}$"},
                    "line": {"enum": list(LINES)},
                    "date_of_loss": {"type": "string", "format": "date"},
                    "reported_date": {"type": "string", "format": "date"},
                    "status": {"enum": list(STATUSES)},
                    "cause": _STR,
                    "reserve": _NUM,
                    "paid": _NUM,
                    "narrative_seed": _STR,
                },
                ["id", "policy_id", "holder_id", "adjuster_id", "line", "date_of_loss", "status", "cause"],
            ),
        },
    },
}

ROSTER_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Meridian Mutual roster (TSV)",
    "description": "Flat id-keyed master-data index. One header row + one row per entity. "
    "Tab-separated, UTF-8, columns in fixed order.",
    "columns": list(ROSTER_COLUMNS),
    "column_docs": {
        "id": "Primary key (PH-/AG-/AD-/policy/claim id).",
        "type": "One of policyholder | agent | adjuster | policy | claim.",
        "name": "Human-readable label for the entity.",
        "line": "Line of business for policy/claim rows; empty otherwise.",
        "parent_id": "Join key to the owning entity (policy.holder_id, claim.policy_id).",
        "status": "Claim status (open/closed/denied); empty for other types.",
        "detail": "Free-text supplementary attributes.",
    },
}


def write_schema(outdir: Path) -> dict:
    outdir = Path(outdir) / "schema"
    outdir.mkdir(parents=True, exist_ok=True)
    model_path = outdir / "model.schema.json"
    roster_path = outdir / "roster.schema.json"
    model_path.write_bytes((json.dumps(MODEL_SCHEMA, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    roster_path.write_bytes((json.dumps(ROSTER_SCHEMA, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return {"model_schema": str(model_path), "roster_schema": str(roster_path)}
