"""The entity / data model — the spine of the corpus.

A deterministic, seeded model generated *first*; every document is a rendering of
it, so cross-document facts are consistent and the golden answers are knowable.

Determinism rules (non-negotiable — see BRIEF.md "Hard rules"):
  * One seeded ``random.Random`` + one seeded ``Faker`` instance, consumed in a
    fixed order. Same seed -> byte-identical ``model.json`` / ``roster.tsv``.
  * NO wall-clock anywhere (no ``date.today()``, no ``Faker.date_of_birth`` which
    is relative to "now"). All dates derive from a fixed ``ANCHOR``.
  * JSON is emitted with ``sort_keys=True`` and a trailing newline; the roster is
    a stable-ordered TSV. Both are diffable in CI.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import string
from dataclasses import asdict, dataclass
from pathlib import Path

from faker import Faker

from . import COMPANY_NAME, SYNTHETIC_MARKER, __version__
from .identity import COUNTRIES, national_id

# Common European makes/models for the insured vehicle on a Motor policy. Make names are
# real (a vehicle's make is legitimate claim data, not an impersonated party).
MAKES_MODELS = (
    ("Volkswagen", "Golf"), ("Renault", "Clio"), ("Peugeot", "208"), ("Ford", "Focus"),
    ("Opel", "Astra"), ("Fiat", "500"), ("Toyota", "Yaris"), ("SEAT", "León"),
    ("Škoda", "Octavia"), ("Citroën", "C3"), ("BMW", "3 Series"), ("Audi", "A3"),
    ("Mercedes-Benz", "A-Class"), ("Volvo", "V40"), ("Nissan", "Qashqai"),
)
VEHICLE_COLOURS = ("white", "black", "silver", "grey", "blue", "red", "green")

# --- fixed temporal anchor (the corpus "now"); a coherent ~2-year window -----
ANCHOR = dt.date(2024, 7, 1)
# SOURCE_DATE_EPOCH for reproducible PDFs is derived from this in render/pdf.py.
ANCHOR_EPOCH = 1719792000  # 2024-07-01T00:00:00Z

LINES = ("personal_auto", "homeowners", "bop")
# European product labels (internal keys are kept stable; only display + id codes are EU).
LINE_LABEL = {
    "personal_auto": "Motor",
    "homeowners": "Household",
    "bop": "Commercial",
}
LINE_CODE = {"personal_auto": "MOT", "homeowners": "HH", "bop": "COM"}

ADJUSTER_SPECIALTIES = ("motor physical damage", "property", "liability", "commercial")

ENDORSEMENTS = {
    "personal_auto": ["RENTAL_REIMB", "ROADSIDE", "GAP", "NEW_CAR_REPL", "UM_UIM"],
    "homeowners": ["WATER_BACKUP", "SCHEDULED_PROP", "ORD_OR_LAW", "SERVICE_LINE", "ID_THEFT"],
    "bop": ["EQUIP_BREAKDOWN", "CYBER", "HIRED_NONOWNED_AUTO", "SPOILAGE", "EPLI"],
}

CAUSES = {
    "personal_auto": ["rear_end_collision", "single_vehicle", "theft", "hail", "vandalism", "animal_strike"],
    "homeowners": ["water_damage", "kitchen_fire", "wind", "hail", "theft", "liability_slip"],
    "bop": ["fire", "burglary", "water_damage", "slip_and_fall", "business_interruption", "equipment_breakdown"],
}

STATUSES = ("closed", "open", "denied")
# Profiles: counts per entity. "slice" is the M1 vertical slice (1 of everything).
PROFILES = {
    "full": dict(holders=80, agents=15, adjusters=10, policies=120, claims=80),
    "sample": dict(holders=6, agents=3, adjusters=2, policies=5, claims=5),
    "slice": dict(holders=1, agents=1, adjusters=1, policies=1, claims=1),
}


# --------------------------------------------------------------------------- #
# Entity records.  frozen dataclasses -> immutable; asdict() -> JSON-ready.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Policyholder:
    id: str
    name: str
    dob: str
    email: str
    phone: str
    street: str
    city: str
    postcode: str
    country: str  # ISO-3166 alpha-2 (DE/FR/ES/IT/NL/IE)
    national_id: str  # synthetic, format-shaped but deliberately invalid (see identity.py)


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    agency: str
    region: str


@dataclass(frozen=True)
class Adjuster:
    id: str
    name: str
    specialty: str


@dataclass(frozen=True)
class Policy:
    id: str
    holder_id: str
    agent_id: str
    line: str
    effective_date: str
    expiry_date: str
    annual_premium: float
    limits: dict
    deductible: float
    endorsements: list
    vehicle: dict | None  # insured vehicle (Motor line only); None otherwise


@dataclass(frozen=True)
class Claim:
    id: str
    policy_id: str
    holder_id: str
    adjuster_id: str
    line: str
    date_of_loss: str
    reported_date: str
    status: str  # closed | open | denied
    cause: str
    reserve: float
    paid: float
    narrative_seed: str


@dataclass(frozen=True)
class Model:
    meta: dict
    policyholders: list
    agents: list
    adjusters: list
    policies: list
    claims: list


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _dollars(rng: random.Random, lo: int, hi: int, step: int = 1) -> float:
    """A deterministic dollar amount in [lo, hi], snapped to ``step``, 2-dp."""
    n = rng.randrange(lo, hi + 1, step)
    return round(float(n), 2)


def _dob(rng: random.Random) -> str:
    """Birth date derived from ANCHOR (never from wall-clock)."""
    age = rng.randint(23, 82)
    year = ANCHOR.year - age
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return dt.date(year, month, day).isoformat()


def _limits(rng: random.Random, line: str) -> dict:
    if line == "personal_auto":
        bi_per_person, bi_per_acc, pd = rng.choice(
            [(50000, 100000, 50000), (100000, 300000, 100000), (250000, 500000, 100000)]
        )
        return {
            "bodily_injury_per_person": bi_per_person,
            "bodily_injury_per_accident": bi_per_acc,
            "property_damage": pd,
        }
    if line == "homeowners":
        dwelling = rng.randrange(250000, 650001, 50000)
        return {
            "dwelling": dwelling,
            "personal_property": int(dwelling * 0.5),
            "personal_liability": rng.choice([100000, 300000, 500000]),
        }
    # bop
    building = rng.randrange(250000, 2000001, 250000)
    return {
        "building": building,
        "business_personal_property": rng.randrange(50000, 500001, 50000),
        "general_liability": rng.choice([500000, 1000000, 2000000]),
    }


def _deductible(rng: random.Random, line: str) -> float:
    if line == "personal_auto":
        return float(rng.choice([250, 500, 1000]))
    return float(rng.choice([1000, 2500, 5000]))


def _premium(rng: random.Random, line: str) -> float:
    base = {"personal_auto": (800, 2200), "homeowners": (900, 2600), "bop": (1500, 6000)}[line]
    return _dollars(rng, base[0], base[1], step=5)


def _plate(rng: random.Random) -> str:
    """A synthetic registration, format-shaped but deliberately INVALID — a 2-letter / 4-digit /
    2-letter pattern is not a live plate format in any corpus country (DE/FR/ES/IT/NL/IE), so it
    cannot match a real registration (same principle as the national IDs in identity.py)."""
    letters = lambda k: "".join(rng.choice(string.ascii_uppercase) for _ in range(k))  # noqa: E731
    return f"{letters(2)}-{rng.randint(1000, 9999)}-{letters(2)}"


def _vehicle(rng: random.Random) -> dict:
    make, model = rng.choice(MAKES_MODELS)
    return {
        "make": make,
        "model": model,
        "year": rng.randint(2008, 2023),
        "colour": rng.choice(VEHICLE_COLOURS),
        "registration": _plate(rng),
    }


def build_model(seed: int, profile: str = "full") -> Model:
    """Seed + profile -> a fully-populated, deterministic :class:`Model`."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose from {sorted(PROFILES)}")
    counts = PROFILES[profile]

    rng = random.Random(seed)
    # One seeded Faker per country locale; calls are consumed in a fixed, rng-driven order.
    fakers = {c.locale: Faker(c.locale) for c in COUNTRIES}
    for fk in fakers.values():
        fk.seed_instance(seed)

    def _oneline(s: str) -> str:
        return " ".join(s.split())

    # 1. Agents — each operates in one European country
    agents: list[Agent] = []
    for i in range(counts["agents"]):
        country = rng.choice(COUNTRIES)
        fk = fakers[country.locale]
        agents.append(
            Agent(
                id=f"AG-{i + 1:03d}",
                name=fk.name(),
                agency=f"{fk.last_name()} {rng.choice(['Insurance Group', 'Assurances', 'Risk Partners', 'Versicherung'])}",
                region=country.name,
            )
        )

    # 2. Adjusters
    adjusters: list[Adjuster] = []
    for i in range(counts["adjusters"]):
        fk = fakers[rng.choice(COUNTRIES).locale]
        adjusters.append(
            Adjuster(
                id=f"AD-{i + 1:03d}",
                name=fk.name(),
                specialty=rng.choice(ADJUSTER_SPECIALTIES),
            )
        )

    # 3. Policyholders — distributed across the European countries
    holders: list[Policyholder] = []
    for i in range(counts["holders"]):
        country = rng.choice(COUNTRIES)
        fk = fakers[country.locale]
        holders.append(
            Policyholder(
                id=f"PH-{i + 1:05d}",
                name=fk.name(),
                dob=_dob(rng),
                email=fk.ascii_safe_email(),
                phone=fk.phone_number(),
                street=_oneline(fk.street_address()),
                city=fk.city(),
                postcode=str(fk.postcode()),
                country=country.code,
                national_id=national_id(country.code, rng),
            )
        )

    # 4. Policies — each derives from a holder + agent; 12-month terms inside the window.
    policies: list[Policy] = []
    for i in range(counts["policies"]):
        line = rng.choice(LINES)
        holder = rng.choice(holders)
        agent = rng.choice(agents)
        eff = ANCHOR + dt.timedelta(days=rng.randint(-540, 180))
        exp = eff + dt.timedelta(days=365)
        endo = ENDORSEMENTS[line]
        n_endo = rng.randint(0, 3)
        policies.append(
            Policy(
                id=f"{LINE_CODE[line]}-{i + 1:07d}",
                holder_id=holder.id,
                agent_id=agent.id,
                line=line,
                effective_date=eff.isoformat(),
                expiry_date=exp.isoformat(),
                annual_premium=_premium(rng, line),
                limits=_limits(rng, line),
                deductible=_deductible(rng, line),
                endorsements=sorted(rng.sample(endo, n_endo)),
                vehicle=_vehicle(rng) if line == "personal_auto" else None,
            )
        )

    # 5. Claims — each attaches to a policy; date_of_loss inside the policy term.
    claims: list[Claim] = []
    for i in range(counts["claims"]):
        policy = rng.choice(policies)
        adjuster = rng.choice(adjusters)
        eff = dt.date.fromisoformat(policy.effective_date)
        exp = dt.date.fromisoformat(policy.expiry_date)
        span = (exp - eff).days
        dol = eff + dt.timedelta(days=rng.randint(1, span - 1))
        reported = dol + dt.timedelta(days=rng.randint(0, 10))
        # Guarantee the first three claims cover closed/open/denied so even the small
        # sample slice exercises every status-dependent document (settlement + denial).
        status = STATUSES[i] if i < len(STATUSES) else rng.choices(STATUSES, weights=[6, 3, 1])[0]
        cause = rng.choice(CAUSES[policy.line])
        if status == "open":
            reserve = _dollars(rng, 2000, 60000, step=50)
            paid = round(reserve * rng.uniform(0.0, 0.4), 2)
        elif status == "closed":
            reserve = 0.0
            paid = _dollars(rng, 500, 50000, step=50)
        else:  # denied
            reserve = 0.0
            paid = 0.0
        claims.append(
            Claim(
                id=f"C-{1000 + i}",
                policy_id=policy.id,
                holder_id=policy.holder_id,
                adjuster_id=adjuster.id,
                line=policy.line,
                date_of_loss=dol.isoformat(),
                reported_date=reported.isoformat(),
                status=status,
                cause=cause,
                reserve=reserve,
                paid=paid,
                narrative_seed=f"{cause.replace('_', ' ')} affecting {policy.line} policy {policy.id} on {dol.isoformat()}",
            )
        )

    meta = {
        "company": COMPANY_NAME,
        "marker": SYNTHETIC_MARKER,
        "synthetic": True,
        "generator_version": __version__,
        "seed": seed,
        "profile": profile,
        "currency": "EUR",
        "region": "Europe",
        "anchor_date": ANCHOR.isoformat(),
        "counts": {
            "policyholders": len(holders),
            "agents": len(agents),
            "adjusters": len(adjusters),
            "policies": len(policies),
            "claims": len(claims),
        },
    }
    return Model(
        meta=meta,
        policyholders=holders,
        agents=agents,
        adjusters=adjusters,
        policies=policies,
        claims=claims,
    )


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def to_json_obj(model: Model) -> dict:
    return {
        "meta": model.meta,
        "policyholders": [asdict(x) for x in model.policyholders],
        "agents": [asdict(x) for x in model.agents],
        "adjusters": [asdict(x) for x in model.adjusters],
        "policies": [asdict(x) for x in model.policies],
        "claims": [asdict(x) for x in model.claims],
    }


def to_json_bytes(model: Model) -> bytes:
    """Canonical, byte-stable JSON encoding (sorted keys, trailing newline)."""
    text = json.dumps(to_json_obj(model), sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


ROSTER_COLUMNS = ("id", "type", "name", "line", "parent_id", "status", "detail")


def roster_rows(model: Model) -> list[tuple]:
    """A flat, id-keyed master-data index — the join target for "who/what owns
    this" questions (mirrors Strata-RAG's roster / register_family pattern)."""
    holder_name = {h.id: h.name for h in model.policyholders}
    rows: list[tuple] = []
    for h in model.policyholders:
        rows.append((h.id, "policyholder", h.name, "", "", "", f"{h.city}, {h.country}"))
    for a in model.agents:
        rows.append((a.id, "agent", a.name, "", "", "", f"{a.agency}; {a.region}"))
    for a in model.adjusters:
        rows.append((a.id, "adjuster", a.name, "", "", "", a.specialty))
    for p in model.policies:
        rows.append(
            (
                p.id,
                "policy",
                f"{LINE_LABEL[p.line]} policy — {holder_name.get(p.holder_id, p.holder_id)}",
                p.line,
                p.holder_id,
                "",
                f"agent={p.agent_id}; eff={p.effective_date}",
            )
        )
    for c in model.claims:
        rows.append(
            (
                c.id,
                "claim",
                f"{LINE_LABEL[c.line]} claim — {c.cause.replace('_', ' ')}",
                c.line,
                c.policy_id,
                c.status,
                f"dol={c.date_of_loss}; adjuster={c.adjuster_id}",
            )
        )
    # Stable order: by type (roster grouping), then id.
    type_order = {t: i for i, t in enumerate(("policyholder", "agent", "adjuster", "policy", "claim"))}
    rows.sort(key=lambda r: (type_order[r[1]], r[0]))
    return rows


def _tsv_escape(value) -> str:
    return str(value).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def to_roster_bytes(model: Model) -> bytes:
    lines = ["\t".join(ROSTER_COLUMNS)]
    for row in roster_rows(model):
        lines.append("\t".join(_tsv_escape(v) for v in row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_model(model: Model, outdir: Path) -> dict:
    """Write model.json + roster.tsv; return {name: path}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    model_path = outdir / "model.json"
    roster_path = outdir / "roster.tsv"
    model_path.write_bytes(to_json_bytes(model))
    roster_path.write_bytes(to_roster_bytes(model))
    return {"model": str(model_path), "roster": str(roster_path)}


# Lookups used by content / golden builders.
def index(model: Model) -> dict:
    return {
        "policyholders": {h.id: h for h in model.policyholders},
        "agents": {a.id: a for a in model.agents},
        "adjusters": {a.id: a for a in model.adjusters},
        "policies": {p.id: p for p in model.policies},
        "claims": {c.id: c for c in model.claims},
    }
