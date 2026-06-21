"""Per-document content builders.

These turn entity facts into the *view-model* a template renders. For M1 the
prose is deterministic and template-driven (no network, fully reproducible).
LLM-authored prose (Claude, cached by ``(seed, doc_id)``) is an M2 enhancement;
the seam is ``narrative_for_claim`` below, which an LLM backend can later override
without changing callers.
"""

from __future__ import annotations

import datetime as dt

from . import COMPANY_NAME, CURRENCY_SYMBOL, SYNTHETIC_MARKER
from .identity import COUNTRY_BY_CODE
from .model import LINE_LABEL, Adjuster, Agent, Claim, Policy, Policyholder


def _add_days(iso_date: str, n: int) -> str:
    """Deterministic date arithmetic on an ISO date string (no wall-clock)."""
    return (dt.date.fromisoformat(iso_date) + dt.timedelta(days=n)).isoformat()


def _eu_date(iso_date: str) -> str:
    """ISO date -> European display format DD/MM/YYYY."""
    d = dt.date.fromisoformat(iso_date)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def _address(holder: Policyholder) -> str:
    country = COUNTRY_BY_CODE.get(holder.country)
    country_name = country.name if country else holder.country
    return f"{holder.street}, {holder.postcode} {holder.city}, {country_name}"


# Human-readable cause labels (also the golden-answer surface form).
CAUSE_LABEL = {
    "rear_end_collision": "rear-end collision",
    "single_vehicle": "single-vehicle accident",
    "theft": "theft",
    "hail": "hail damage",
    "vandalism": "vandalism",
    "animal_strike": "animal strike",
    "water_damage": "water damage",
    "kitchen_fire": "kitchen fire",
    "wind": "wind damage",
    "liability_slip": "slip-and-fall liability",
    "fire": "fire",
    "burglary": "burglary",
    "slip_and_fall": "slip-and-fall",
    "business_interruption": "business interruption",
    "equipment_breakdown": "equipment breakdown",
}


def cause_label(cause: str) -> str:
    return CAUSE_LABEL.get(cause, cause.replace("_", " "))


def _money(x: float) -> str:
    return f"{CURRENCY_SYMBOL}{x:,.2f}"


def _vehicle_str(policy: Policy) -> str | None:
    v = policy.vehicle
    if not v:
        return None
    return f"{v['make']} {v['model']} ({v['year']}, {v['colour']}) — reg {v['registration']}"


def _limits_lines(policy: Policy) -> list[tuple[str, str]]:
    pretty = {
        "bodily_injury_per_person": "Bodily injury — per person",
        "bodily_injury_per_accident": "Bodily injury — per accident",
        "property_damage": "Property damage",
        "dwelling": "Dwelling (Coverage A)",
        "personal_property": "Personal property (Coverage C)",
        "personal_liability": "Personal liability",
        "building": "Building",
        "business_personal_property": "Business personal property",
        "general_liability": "General liability aggregate",
    }
    return [(pretty.get(k, k), _money(float(v))) for k, v in policy.limits.items()]


# Endorsement code -> human description (for the endorsements document).
ENDORSEMENT_DESC = {
    "RENTAL_REIMB": "Rental Reimbursement — pays for a rental vehicle while a covered auto is being repaired.",
    "ROADSIDE": "Roadside Assistance — towing and labor at the place of disablement.",
    "GAP": "Loan/Lease Gap Coverage — pays the difference between the auto's actual cash value and the loan balance.",
    "NEW_CAR_REPL": "New Car Replacement — replaces a totaled new vehicle with a comparable new model.",
    "UM_UIM": "Uninsured/Underinsured Motorist — covers injury caused by an at-fault driver lacking adequate limits.",
    "WATER_BACKUP": "Water Backup and Sump Overflow — loss from backup of sewers, drains, or sump-pump failure.",
    "SCHEDULED_PROP": "Scheduled Personal Property — itemized coverage for high-value articles above standard limits.",
    "ORD_OR_LAW": "Ordinance or Law — added cost to rebuild to current building codes after a covered loss.",
    "SERVICE_LINE": "Service Line Coverage — damage to underground utility lines serving the residence.",
    "ID_THEFT": "Identity Theft Expense — expenses to restore identity following a theft event.",
    "EQUIP_BREAKDOWN": "Equipment Breakdown — sudden mechanical or electrical breakdown of covered equipment.",
    "CYBER": "Cyber Liability — first- and third-party costs arising from a data breach or cyber event.",
    "HIRED_NONOWNED_AUTO": "Hired and Non-Owned Auto — liability for autos hired or used in the business but not owned.",
    "SPOILAGE": "Spoilage Coverage — loss of perishable stock from a covered breakdown or power interruption.",
    "EPLI": "Employment Practices Liability — claims of wrongful employment acts by employees.",
}


# Deterministic per-line coverage clauses (kept short; realism over completeness).
_CLAUSES = {
    "personal_auto": [
        "We will pay damages for bodily injury and property damage for which any insured "
        "becomes legally responsible because of an auto accident, subject to the limits shown "
        "on the Declarations.",
        "Collision and Other Than Collision (comprehensive) coverages apply to a covered auto "
        "less the applicable deductible shown on the Declarations.",
    ],
    "homeowners": [
        "We insure the dwelling described on the Declarations against direct physical loss, "
        "except as excluded, up to the Coverage A limit shown.",
        "Personal property is covered for the perils insured against, subject to the deductible "
        "stated on the Declarations.",
    ],
    "bop": [
        "We will pay for direct physical loss of or damage to Covered Property caused by or "
        "resulting from a Covered Cause of Loss, subject to the limits of insurance shown.",
        "Business income and extra expense coverage applies during the period of restoration "
        "following a covered suspension of operations.",
    ],
}


# Shared contract language (line-independent conditions / exclusions).
_CONDITIONS = [
    "Premium. The premium shown on the Declarations is payable as a condition of this insurance; "
    "non-payment may result in cancellation in accordance with the policy terms.",
    "Duties After Loss. In the event of a loss, the insured must give prompt notice, protect the "
    "property from further damage, cooperate in the investigation, and submit a signed proof of loss.",
    "Concealment or Fraud. This policy is void if any insured has intentionally concealed or "
    "misrepresented a material fact concerning this insurance or a claim under it.",
]
_EXCLUSIONS = {
    "personal_auto": "We do not cover loss arising from racing or speed contests, use as a public "
    "livery or for ride-share without the applicable endorsement, or intentional damage by an insured.",
    "homeowners": "We do not cover loss caused by flood, earth movement, neglect, ordinance or law "
    "(unless endorsed), or wear and tear.",
    "bop": "We do not cover loss caused by flood or earth movement, dishonest acts by the insured, "
    "wear and tear, or loss of business income outside the period of restoration.",
}


def declarations_document(model_meta: dict, policy: Policy, holder: Policyholder, agent: Agent) -> dict:
    """View-model for the policy Declarations page (PDF)."""
    endo = ", ".join(policy.endorsements) if policy.endorsements else "None"
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": f"{LINE_LABEL[policy.line]} Policy — Declarations",
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "holder_address": _address(holder),
        "agent_name": agent.name,
        "agency": agent.agency,
        "effective_date": _eu_date(policy.effective_date),
        "expiry_date": _eu_date(policy.expiry_date),
        "annual_premium": _money(policy.annual_premium),
        "deductible": _money(policy.deductible),
        "limits": _limits_lines(policy),
        "endorsements": endo,
        "vehicle": _vehicle_str(policy),
    }


def contract_document(model_meta: dict, policy: Policy, holder: Policyholder) -> dict:
    """View-model for the full policy contract (docx). Sections feed the renderer."""
    sections = [
        ("Insuring Agreement", list(_CLAUSES[policy.line])),
        (
            "Definitions",
            [
                '"Insured" means the named insured shown on the Declarations and, where applicable, '
                "resident relatives and others defined by the policy.",
                '"Covered Cause of Loss" means a peril insured against under this policy and not '
                "otherwise excluded.",
            ],
        ),
        ("Conditions", list(_CONDITIONS)),
        ("Exclusions", [_EXCLUSIONS[policy.line]]),
    ]
    return {
        "doc_title": f"{LINE_LABEL[policy.line]} Policy — Contract",
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "effective_date": _eu_date(policy.effective_date),
        "expiry_date": _eu_date(policy.expiry_date),
        "sections": sections,
    }


def endorsements_document(model_meta: dict, policy: Policy, holder: Policyholder) -> dict:
    """View-model for the endorsements schedule (PDF)."""
    rows = [(code, ENDORSEMENT_DESC.get(code, code)) for code in policy.endorsements]
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": f"{LINE_LABEL[policy.line]} Policy — Endorsement Schedule",
        "policy_id": policy.id,
        "holder_name": holder.name,
        "rows": rows,
    }


def schedule_document(model_meta: dict, policy: Policy, holder: Policyholder) -> dict:
    """View-model for the coverage schedule (PDF)."""
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": f"{LINE_LABEL[policy.line]} Policy — Coverage Schedule",
        "policy_id": policy.id,
        "holder_name": holder.name,
        "effective_date": _eu_date(policy.effective_date),
        "expiry_date": _eu_date(policy.expiry_date),
        "deductible": _money(policy.deductible),
        "annual_premium": _money(policy.annual_premium),
        "limits": _limits_lines(policy),
    }


def narrative_for_claim(claim: Claim, holder: Policyholder, policy: Policy) -> str:
    """The FNOL loss-description prose. Deterministic template (M1).

    This is the documented seam for M2 LLM content: a backend may replace the
    body with Claude-authored prose conditioned on these same facts, cached by
    ``(seed, claim.id)``. The asserted facts (cause, date) must stay consistent.
    """
    cause = cause_label(claim.cause)
    # A deterministic variant chosen from the claim id (stable, no RNG state).
    variant = sum(ord(ch) for ch in claim.id) % 2
    dol = _eu_date(claim.date_of_loss)
    if variant == 0:
        lead = (
            f"On {dol}, the insured reported a loss involving {cause} "
            f"under {LINE_LABEL[policy.line]} policy {policy.id}."
        )
    else:
        lead = (
            f"The insured contacted us regarding {cause} that occurred on {dol}, "
            f"associated with {LINE_LABEL[policy.line]} policy {policy.id}."
        )
    detail = {
        "personal_auto": "Initial reports describe damage to the insured vehicle; no injuries were noted at first notice.",
        "homeowners": "The insured reports damage to the residence premises and requests inspection.",
        "bop": "The insured reports damage at the business premises and possible interruption of operations.",
    }[policy.line]
    return f"{lead} {detail} A claim has been established for review by the assigned adjuster."


def fnol_document(
    model_meta: dict,
    claim: Claim,
    policy: Policy,
    holder: Policyholder,
    adjuster: Adjuster,
) -> dict:
    """View-model for the First Notice of Loss (FNOL) PDF."""
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": "First Notice of Loss (FNOL)",
        "claim_id": claim.id,
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "holder_phone": holder.phone,
        "holder_email": holder.email,
        "date_of_loss": _eu_date(claim.date_of_loss),
        "reported_date": _eu_date(claim.reported_date),
        "status": claim.status,
        "cause_label": cause_label(claim.cause),
        "adjuster_name": adjuster.name,
        "adjuster_specialty": adjuster.specialty,
        "reserve": _money(claim.reserve),
        "vehicle": _vehicle_str(policy),
        "narrative": narrative_for_claim(claim, holder, policy),
    }


# --- claim handling documents (issue #6) ----------------------------------- #
_ADJUSTER_FINDINGS = {
    "personal_auto": "Inspection confirms damage to the insured vehicle consistent with the reported {cause}. Photographs and the repair estimate are on file.",
    "homeowners": "Site inspection of the residence confirms damage consistent with the reported {cause}. The scope of repair is documented in the attached estimate.",
    "bop": "Inspection of the business premises confirms a loss consistent with the reported {cause}. The impact on operations has been assessed and documented.",
}


def adjuster_report_document(model_meta: dict, claim: Claim, policy: Policy, holder: Policyholder, adjuster: Adjuster) -> dict:
    """View-model for the adjuster's report (PDF) — generated for every claim."""
    cause = cause_label(claim.cause)
    if claim.status == "closed":
        disposition = "Closed — paid"
        recommendation = (
            f"Coverage applies. Claim resolved; payment of {_money(claim.paid)} issued to the insured, "
            f"net of the {_money(policy.deductible)} deductible."
        )
    elif claim.status == "open":
        disposition = "Open — under review"
        recommendation = (
            f"Coverage appears to apply. A reserve of {_money(claim.reserve)} has been established pending "
            "completion of repairs and final documentation."
        )
    else:  # denied
        disposition = "Denied"
        recommendation = (
            "Based on the investigation, the loss is not covered under the policy terms; denial is "
            "recommended. See the denial letter issued to the insured."
        )
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": "Adjuster Report",
        "claim_id": claim.id,
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "adjuster_name": adjuster.name,
        "adjuster_specialty": adjuster.specialty,
        "date_of_loss": _eu_date(claim.date_of_loss),
        "reported_date": _eu_date(claim.reported_date),
        "cause_label": cause,
        "status": claim.status,
        "reserve": _money(claim.reserve),
        "paid": _money(claim.paid),
        "findings": _ADJUSTER_FINDINGS[policy.line].format(cause=cause),
        "recommendation": recommendation,
        "disposition": disposition,
    }


_ESTIMATE_ITEMS = {
    "personal_auto": ["Replacement parts", "Body labor", "Paint & materials"],
    "homeowners": ["Materials", "Labor", "Debris removal & cleanup"],
    "bop": ["Property repair", "Equipment & fixtures", "Restoration labor"],
}
_ESTIMATE_FRACTIONS = (0.5, 0.35, 0.15)


def estimate_base(claim: Claim) -> float:
    """Net amount payable on a claim — the model figure a settlement pays out."""
    return claim.paid if claim.status == "closed" else claim.reserve


def estimate_document(model_meta: dict, claim: Claim, policy: Policy, holder: Policyholder) -> dict:
    """View-model for the repair/damage estimate (PDF).

    Gross repair cost = net payable + deductible, so the net (after deductible) equals the
    model's payout figure and the settlement letter stays consistent. Only meaningful for
    claims with a positive amount (open/closed); denied claims get no estimate.
    """
    base = estimate_base(claim)
    gross = round(base + policy.deductible, 2)
    labels = _ESTIMATE_ITEMS[policy.line]
    amounts: list[float] = []
    running = 0.0
    for i, frac in enumerate(_ESTIMATE_FRACTIONS):
        if i < len(_ESTIMATE_FRACTIONS) - 1:
            amt = round(gross * frac, 2)
            running += amt
        else:
            amt = round(gross - running, 2)  # last line absorbs rounding so the column sums exactly
        amounts.append(amt)
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": "Damage / Repair Estimate",
        "claim_id": claim.id,
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "date_of_loss": _eu_date(claim.date_of_loss),
        "cause_label": cause_label(claim.cause),
        "rows": list(zip(labels, [_money(a) for a in amounts])),
        "gross_total": _money(gross),
        "deductible": _money(policy.deductible),
        "net_payable": _money(base),
    }


def settlement_letter_document(model_meta: dict, claim: Claim, policy: Policy, holder: Policyholder, adjuster: Adjuster) -> dict:
    """View-model for the settlement letter (PDF) — closed claims with a payout."""
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": "Claim Settlement",
        "letter_date": _eu_date(_add_days(claim.reported_date, 30)),
        "claim_id": claim.id,
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "holder_address": _address(holder),
        "date_of_loss": _eu_date(claim.date_of_loss),
        "cause_label": cause_label(claim.cause),
        "paid": _money(claim.paid),
        "deductible": _money(policy.deductible),
        "adjuster_name": adjuster.name,
    }


# Deterministic denial rationales (the model has no per-claim reason; chosen by claim id).
_DENIAL_REASONS = [
    "the cause of loss falls within an exclusion stated in your policy",
    "the loss occurred outside the effective period of coverage",
    "the documentation submitted was insufficient to establish a covered loss",
    "the damage claimed is attributable to wear and tear, which the policy does not cover",
]


def denial_reason(claim: Claim) -> str:
    return _DENIAL_REASONS[sum(ord(c) for c in claim.id) % len(_DENIAL_REASONS)]


def denial_letter_document(model_meta: dict, claim: Claim, policy: Policy, holder: Policyholder, adjuster: Adjuster) -> dict:
    """View-model for the denial letter (PDF) — denied claims."""
    return {
        "marker": SYNTHETIC_MARKER,
        "company": COMPANY_NAME,
        "doc_title": "Claim Determination — Denial",
        "letter_date": _eu_date(_add_days(claim.reported_date, 21)),
        "claim_id": claim.id,
        "policy_id": policy.id,
        "line_label": LINE_LABEL[policy.line],
        "holder_name": holder.name,
        "holder_address": _address(holder),
        "date_of_loss": _eu_date(claim.date_of_loss),
        "cause_label": cause_label(claim.cause),
        "reason": denial_reason(claim),
        "adjuster_name": adjuster.name,
    }
