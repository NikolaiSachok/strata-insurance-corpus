"""Corpus-level tabular documents (issue #7).

These aggregate across the whole model into the spreadsheets a RAG system answers
*aggregation / metadata* questions over: loss run, reserve register, premium register,
and an agent commission summary. Tables are built deterministically (stable row order);
the aggregate helpers are the single source of truth for both the sheets and the golden
aggregation answers, so the two can't drift.
"""

from __future__ import annotations

from .model import LINE_LABEL, Model

# Synthetic commission rates by line (a generation detail, not a model field).
COMMISSION_RATE = {"personal_auto": 0.10, "homeowners": 0.12, "bop": 0.15}


def _holder_names(model: Model) -> dict:
    return {h.id: h.name for h in model.policyholders}


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def loss_run(model: Model) -> dict:
    rows = [
        [c.id, c.policy_id, LINE_LABEL[c.line], c.date_of_loss, c.cause.replace("_", " "), c.status, c.reserve, c.paid]
        for c in sorted(model.claims, key=lambda c: c.id)
    ]
    return {
        "title": "Loss Run",
        "headers": ["Claim", "Policy", "Line", "Date of loss", "Cause", "Status", "Reserve", "Paid"],
        "rows": rows,
        "currency_cols": [6, 7],
    }


def reserve_register(model: Model) -> dict:
    rows = [
        [c.id, c.policy_id, LINE_LABEL[c.line], c.adjuster_id, c.date_of_loss, c.reserve]
        for c in sorted(model.claims, key=lambda c: c.id)
        if c.status == "open"
    ]
    return {
        "title": "Reserve Register",
        "headers": ["Claim", "Policy", "Line", "Adjuster", "Date of loss", "Reserve"],
        "rows": rows,
        "currency_cols": [5],
    }


def premium_register(model: Model) -> dict:
    names = _holder_names(model)
    rows = [
        [p.id, names.get(p.holder_id, p.holder_id), LINE_LABEL[p.line], p.effective_date, p.expiry_date, p.annual_premium]
        for p in sorted(model.policies, key=lambda p: p.id)
    ]
    return {
        "title": "Premium Register",
        "headers": ["Policy", "Named insured", "Line", "Effective", "Expiry", "Annual premium"],
        "rows": rows,
        "currency_cols": [5],
    }


def commission_summary(model: Model) -> dict:
    by_agent = {a.id: {"agent": a, "policies": 0, "premium": 0.0, "commission": 0.0} for a in model.agents}
    for p in model.policies:
        rec = by_agent.get(p.agent_id)
        if rec is None:
            continue
        rec["policies"] += 1
        rec["premium"] += p.annual_premium
        rec["commission"] += p.annual_premium * COMMISSION_RATE[p.line]
    rows = []
    for aid in sorted(by_agent):
        rec = by_agent[aid]
        a = rec["agent"]
        rows.append([a.id, a.name, a.agency, a.region, rec["policies"], round(rec["premium"], 2), round(rec["commission"], 2)])
    return {
        "title": "Agent Commission Summary",
        "headers": ["Agent", "Name", "Agency", "Region", "Policies", "Total premium", "Commission"],
        "rows": rows,
        "currency_cols": [5, 6],
    }


# --------------------------------------------------------------------------- #
# Aggregates — single source of truth for the golden aggregation answers
# --------------------------------------------------------------------------- #
def total_open_reserve(model: Model) -> float:
    return round(sum(c.reserve for c in model.claims if c.status == "open"), 2)


def total_annual_premium(model: Model) -> float:
    return round(sum(p.annual_premium for p in model.policies), 2)


def open_claim_count(model: Model) -> int:
    return sum(1 for c in model.claims if c.status == "open")
