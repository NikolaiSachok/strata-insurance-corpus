"""Corpus-level knowledge-base documents (issue #8).

Reference docs a RAG system answers *semantic KB* questions over: underwriting
guidelines, the claims-handling manual, and a customer FAQ. Content is deterministic
and coherent with the model's domain (the same lines, endorsements, claim statuses,
and process), but is general reference text rather than per-entity data.

Each builder returns a ``KBDoc`` dict ``{title, intro, sections}`` where a section is
``{heading, paragraphs: [str], bullets: [str]?}`` — rendered to Markdown or .docx.
"""

from __future__ import annotations

from . import COMPANY_NAME
from .content import ENDORSEMENT_DESC
from .model import LINE_LABEL, LINES

LINES_SENTENCE = ", ".join(LINE_LABEL[ln] for ln in LINES)


def underwriting_guidelines() -> dict:
    endo_bullets = [f"{code} — {desc}" for code, desc in ENDORSEMENT_DESC.items()]
    return {
        "title": "Underwriting Guidelines",
        "intro": (
            f"These guidelines describe {COMPANY_NAME}'s underwriting standards. They are an internal "
            "reference for agents and underwriters and do not modify any policy contract."
        ),
        "sections": [
            {
                "heading": "Lines of Business",
                "paragraphs": [f"{COMPANY_NAME} underwrites three personal and small-commercial lines: {LINES_SENTENCE}."],
            },
            {
                "heading": "Eligibility",
                "paragraphs": ["Risks are accepted subject to the following general criteria:"],
                "bullets": [
                    "Personal Auto: licensed drivers with an acceptable motor-vehicle record; rated by vehicle and territory.",
                    "Homeowners: owner-occupied dwellings in insurable condition; subject to property inspection.",
                    "Businessowners (BOP): eligible small businesses within approved class codes and size limits.",
                ],
            },
            {
                "heading": "Limits and Deductibles",
                "paragraphs": [
                    "Personal Auto liability is offered at 50/100/50, 100/300/100, and 250/500/100 limits, with "
                    "physical-damage deductibles of $250, $500, or $1,000.",
                    "Homeowners dwelling limits range from $250,000 to $650,000 with deductibles of $1,000, $2,500, "
                    "or $5,000; personal liability is offered at $100,000, $300,000, or $500,000.",
                    "BOP building limits range up to $2,000,000 with general-liability limits of $500,000, "
                    "$1,000,000, or $2,000,000.",
                ],
            },
            {
                "heading": "Available Endorsements",
                "paragraphs": ["The following endorsements may be added to a policy where eligible:"],
                "bullets": endo_bullets,
            },
        ],
    }


def claims_manual() -> dict:
    return {
        "title": "Claims Handling Manual",
        "intro": (
            f"This manual describes how {COMPANY_NAME} handles a claim from first notice to resolution. "
            "It is a procedural reference for claims staff."
        ),
        "sections": [
            {
                "heading": "Claim Lifecycle",
                "paragraphs": ["Every claim moves through a standard sequence:"],
                "bullets": [
                    "First Notice of Loss (FNOL): the loss is reported and a claim is established.",
                    "Assignment: an adjuster is assigned based on line and specialty.",
                    "Investigation: the adjuster inspects the loss and documents findings in an adjuster report.",
                    "Estimate: a damage/repair estimate is prepared where the loss is covered.",
                    "Resolution: the claim is settled (payment issued) or denied (with a determination letter).",
                ],
            },
            {
                "heading": "Reserving",
                "paragraphs": [
                    "An open claim carries a reserve representing the estimated remaining cost to resolve it. "
                    "Reserves are reviewed as new information arrives and are released when the claim closes."
                ],
            },
            {
                "heading": "Settlement and Deductibles",
                "paragraphs": [
                    "When a claim is approved, payment is issued for the covered loss net of the policy deductible. "
                    "The net amount payable equals the gross repair estimate less the deductible shown on the policy."
                ],
            },
            {
                "heading": "Denials",
                "paragraphs": [
                    "A claim may be denied when the loss is excluded, falls outside the coverage period, or is not "
                    "adequately documented. A denial letter stating the basis is sent to the insured, who may request a review."
                ],
            },
        ],
    }


def customer_faq() -> dict:
    return {
        "title": "Customer FAQ",
        "intro": f"Answers to common questions for {COMPANY_NAME} policyholders.",
        "sections": [
            {
                "heading": "How do I file a claim?",
                "paragraphs": [
                    "Contact us to report the loss. We will record a First Notice of Loss, establish a claim, and "
                    "assign an adjuster who will guide you through the rest of the process."
                ],
            },
            {
                "heading": "What happens after I report a claim?",
                "paragraphs": [
                    "Your assigned adjuster investigates the loss, prepares an estimate where the loss is covered, and "
                    "then either issues a settlement payment or sends a written determination explaining a denial."
                ],
            },
            {
                "heading": "How is my settlement amount calculated?",
                "paragraphs": [
                    "For a covered loss, we pay the cost to repair or replace the damaged property less your policy "
                    "deductible. The deductible is shown on your declarations page."
                ],
            },
            {
                "heading": "What lines of insurance do you offer?",
                "paragraphs": [f"We offer {LINES_SENTENCE}."],
            },
        ],
    }
