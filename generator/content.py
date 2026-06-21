"""Per-document content builders.

These turn entity facts into the *view-model* a template renders. For M1 the
prose is deterministic and template-driven (no network, fully reproducible).
LLM-authored prose (Claude, cached by ``(seed, doc_id)``) is an M2 enhancement;
the seam is ``narrative_for_claim`` below, which an LLM backend can later override
without changing callers.
"""

from __future__ import annotations

from . import COMPANY_NAME, SYNTHETIC_MARKER
from .model import LINE_LABEL, Adjuster, Agent, Claim, Policy, Policyholder

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
    return f"${x:,.2f}"


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
        "holder_address": f"{holder.street}, {holder.city}, {holder.state} {holder.zip}",
        "agent_name": agent.name,
        "agency": agent.agency,
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
        "annual_premium": _money(policy.annual_premium),
        "deductible": _money(policy.deductible),
        "limits": _limits_lines(policy),
        "endorsements": endo,
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
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
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
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
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
    if variant == 0:
        lead = (
            f"On {claim.date_of_loss}, the insured reported a loss involving {cause} "
            f"under {LINE_LABEL[policy.line]} policy {policy.id}."
        )
    else:
        lead = (
            f"The insured contacted us regarding {cause} that occurred on {claim.date_of_loss}, "
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
        "date_of_loss": claim.date_of_loss,
        "reported_date": claim.reported_date,
        "status": claim.status,
        "cause_label": cause_label(claim.cause),
        "adjuster_name": adjuster.name,
        "adjuster_specialty": adjuster.specialty,
        "reserve": _money(claim.reserve),
        "narrative": narrative_for_claim(claim, holder, policy),
    }
