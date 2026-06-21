"""CLI entrypoint for the generator.

    python -m generator.run --seed 42 --out corpus/ --profile full

Pipeline (see BRIEF.md "Generation pipeline"):
  1. model gen      -> model.json + roster.tsv + schema/
  2. content + render-> docs/ (policy PDF per policy, FNOL PDF per claim)
  3. provenance      -> per-doc asserted facts
  4. manifest        -> manifest.json
  5. golden          -> golden.jsonl (semantic class, M1)

Everything is deterministic: same (seed, profile) -> byte-stable corpus.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .content import (
    adjuster_report_document,
    cause_label,
    contract_document,
    declarations_document,
    denial_letter_document,
    endorsements_document,
    estimate_base,
    estimate_document,
    fnol_document,
    schedule_document,
    settlement_letter_document,
)
from . import tabular
from .golden import build_golden, write_golden
from .manifest import write_manifest
from .model import ANCHOR_EPOCH, build_model, index, write_model
from .provenance import Assertion, DocRecord, sha256_file
from .schema import write_schema


def _money(x: float) -> str:
    """Match content._money so manifest provenance values equal the rendered text."""
    return f"${x:,.2f}"


# Generated artifacts removed before each run so regeneration leaves no orphans.
# Anything else in the out dir (notably a committed README.md) is preserved.
_GENERATED = ("docs", "schema", "model.json", "roster.tsv", "manifest.json", "golden.jsonl")


def _clean_generated(out: Path) -> None:
    import shutil

    for name in _GENERATED:
        target = out / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def generate(seed: int, out: Path, profile: str, render: bool = True) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    _clean_generated(out)

    # 1. model + schema
    model = build_model(seed, profile)
    paths = write_model(model, out)
    write_schema(out)
    idx = index(model)

    records: list[DocRecord] = []
    fnol_doc_for_claim: dict[str, str] = {}
    decl_doc_for_policy: dict[str, str] = {}
    settlement_doc_for_claim: dict[str, str] = {}
    tabular_doc_ids: dict[str, str] = {}

    if render:
        from .render.docx import write_contract_docx  # lazy imports
        from .render.pdf import write_pdf

        def emit_pdf(doc_id, doc_type, template, ctx, rel, entity_ids, asserts):
            write_pdf(template, ctx, out / rel, ANCHOR_EPOCH)
            records.append(
                DocRecord(
                    doc_id=doc_id,
                    doc_type=doc_type,
                    format="pdf",
                    path=rel,
                    entity_ids=entity_ids,
                    asserts=asserts,
                    sha256=sha256_file(out / rel),
                )
            )

        # 2+3. policy family: declarations (PDF), contract (docx), endorsements (PDF), schedule (PDF)
        for policy in model.policies:
            holder = idx["policyholders"][policy.holder_id]
            agent = idx["agents"][policy.agent_id]
            base_ids = [policy.id, policy.holder_id, policy.agent_id]

            # Declarations page (PDF)
            decl_id = f"DOC-{policy.id}-DEC"
            decl_rel = f"docs/policy/{policy.id}-declarations.pdf"
            write_pdf("declarations.html.j2", declarations_document(model.meta, policy, holder, agent), out / decl_rel, ANCHOR_EPOCH)
            decl_doc_for_policy[policy.id] = decl_id
            records.append(
                DocRecord(
                    doc_id=decl_id,
                    doc_type="policy_declarations",
                    format="pdf",
                    path=decl_rel,
                    entity_ids=base_ids,
                    asserts=[
                        Assertion(policy.id, "annual_premium", _money(policy.annual_premium)),
                        Assertion(policy.id, "effective_date", policy.effective_date),
                        Assertion(policy.id, "expiry_date", policy.expiry_date),
                        Assertion(policy.id, "line", policy.line),
                    ],
                    sha256=sha256_file(out / decl_rel),
                )
            )

            # Full policy contract (docx)
            contract_rel = f"docs/policy/{policy.id}-contract.docx"
            write_contract_docx(contract_document(model.meta, policy, holder), out / contract_rel)
            records.append(
                DocRecord(
                    doc_id=f"DOC-{policy.id}-CONTRACT",
                    doc_type="policy_contract",
                    format="docx",
                    path=contract_rel,
                    entity_ids=[policy.id, policy.holder_id],
                    asserts=[Assertion(policy.id, "line", policy.line)],
                    sha256=sha256_file(out / contract_rel),
                )
            )

            # Endorsement schedule (PDF)
            endo_rel = f"docs/policy/{policy.id}-endorsements.pdf"
            write_pdf("endorsements.html.j2", endorsements_document(model.meta, policy, holder), out / endo_rel, ANCHOR_EPOCH)
            records.append(
                DocRecord(
                    doc_id=f"DOC-{policy.id}-ENDORSEMENTS",
                    doc_type="policy_endorsements",
                    format="pdf",
                    path=endo_rel,
                    entity_ids=[policy.id, policy.holder_id],
                    asserts=[Assertion(policy.id, "endorsements", ", ".join(policy.endorsements) or "None")],
                    sha256=sha256_file(out / endo_rel),
                )
            )

            # Coverage schedule (PDF)
            sched_rel = f"docs/policy/{policy.id}-schedule.pdf"
            write_pdf("schedule.html.j2", schedule_document(model.meta, policy, holder), out / sched_rel, ANCHOR_EPOCH)
            records.append(
                DocRecord(
                    doc_id=f"DOC-{policy.id}-SCHEDULE",
                    doc_type="policy_schedule",
                    format="pdf",
                    path=sched_rel,
                    entity_ids=[policy.id, policy.holder_id],
                    asserts=[Assertion(policy.id, "deductible", _money(policy.deductible))],
                    sha256=sha256_file(out / sched_rel),
                )
            )

        # Claim family: FNOL (all) + adjuster report (all) + estimate (open/closed)
        # + settlement letter (closed) | denial letter (denied)
        for claim in model.claims:
            policy = idx["policies"][claim.policy_id]
            holder = idx["policyholders"][claim.holder_id]
            adjuster = idx["adjusters"][claim.adjuster_id]
            claim_ids = [claim.id, claim.policy_id, claim.holder_id, claim.adjuster_id]

            # FNOL
            fnol_id = f"DOC-{claim.id}-FNOL"
            fnol_doc_for_claim[claim.id] = fnol_id
            emit_pdf(
                fnol_id, "fnol", "fnol.html.j2",
                fnol_document(model.meta, claim, policy, holder, adjuster),
                f"docs/claim/{claim.id}-fnol.pdf", claim_ids,
                [
                    Assertion(claim.id, "cause", cause_label(claim.cause)),
                    Assertion(claim.id, "date_of_loss", claim.date_of_loss),
                    Assertion(claim.id, "status", claim.status),
                ],
            )

            # Adjuster report
            emit_pdf(
                f"DOC-{claim.id}-ADJ", "adjuster_report", "adjuster_report.html.j2",
                adjuster_report_document(model.meta, claim, policy, holder, adjuster),
                f"docs/claim/{claim.id}-adjuster-report.pdf", claim_ids,
                [
                    Assertion(claim.id, "cause", cause_label(claim.cause)),
                    Assertion(claim.id, "status", claim.status),
                    Assertion(claim.id, "adjuster_id", claim.adjuster_id),
                ],
            )

            # Repair/damage estimate (claims with a payable amount)
            if claim.status in ("open", "closed"):
                emit_pdf(
                    f"DOC-{claim.id}-ESTIMATE", "estimate", "estimate.html.j2",
                    estimate_document(model.meta, claim, policy, holder),
                    f"docs/claim/{claim.id}-estimate.pdf", claim_ids,
                    [Assertion(claim.id, "estimate_net_payable", _money(estimate_base(claim)))],
                )

            # Settlement (closed) | denial (denied)
            if claim.status == "closed":
                settle_id = f"DOC-{claim.id}-SETTLEMENT"
                settlement_doc_for_claim[claim.id] = settle_id
                emit_pdf(
                    settle_id, "settlement_letter", "settlement_letter.html.j2",
                    settlement_letter_document(model.meta, claim, policy, holder, adjuster),
                    f"docs/claim/{claim.id}-settlement-letter.pdf", claim_ids,
                    [
                        Assertion(claim.id, "paid", _money(claim.paid)),
                        Assertion(claim.id, "status", claim.status),
                    ],
                )
            elif claim.status == "denied":
                emit_pdf(
                    f"DOC-{claim.id}-DENIAL", "denial_letter", "denial_letter.html.j2",
                    denial_letter_document(model.meta, claim, policy, holder, adjuster),
                    f"docs/claim/{claim.id}-denial-letter.pdf", claim_ids,
                    [Assertion(claim.id, "status", "denied")],
                )

        # Tabular family (corpus-level): registers in xlsx + commission in csv
        from .render.sheets import write_csv, write_xlsx

        tab_specs = [
            ("DOC-TAB-LOSS-RUN", "loss_run", "xlsx", "docs/tabular/loss-run.xlsx",
             lambda p: write_xlsx([tabular.loss_run(model)], p), [c.id for c in model.claims]),
            ("DOC-TAB-RESERVE", "reserve_register", "xlsx", "docs/tabular/reserve-register.xlsx",
             lambda p: write_xlsx([tabular.reserve_register(model)], p), [c.id for c in model.claims if c.status == "open"]),
            ("DOC-TAB-PREMIUM", "premium_register", "xlsx", "docs/tabular/premium-register.xlsx",
             lambda p: write_xlsx([tabular.premium_register(model)], p), [p.id for p in model.policies]),
            ("DOC-TAB-COMMISSION", "commission_summary", "csv", "docs/tabular/commission-summary.csv",
             lambda p: write_csv(tabular.commission_summary(model), p), [a.id for a in model.agents]),
        ]
        for doc_id, doc_type, fmt, rel, writer, entity_ids in tab_specs:
            writer(out / rel)
            tabular_doc_ids[doc_type] = doc_id
            records.append(
                DocRecord(
                    doc_id=doc_id, doc_type=doc_type, format=fmt, path=rel,
                    entity_ids=entity_ids, asserts=[], sha256=sha256_file(out / rel),
                )
            )

    # 4. manifest
    write_manifest(out, model.meta, records)

    # 5. golden
    golden = build_golden(
        model, fnol_doc_for_claim, decl_doc_for_policy, settlement_doc_for_claim, tabular_doc_ids
    )
    write_golden(out, golden)

    return {
        "out": str(out),
        "model": paths["model"],
        "roster": paths["roster"],
        "documents": len(records),
        "golden_questions": len(golden),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="generator.run", description="Generate the synthetic insurance corpus.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("corpus"))
    ap.add_argument("--profile", choices=["full", "sample", "slice"], default="full")
    ap.add_argument("--no-render", action="store_true", help="model + schema only (skip PDFs)")
    args = ap.parse_args(argv)

    summary = generate(args.seed, args.out, args.profile, render=not args.no_render)
    print(
        f"[generate] seed={args.seed} profile={args.profile} -> {summary['out']}\n"
        f"           model={summary['model']}\n"
        f"           roster={summary['roster']}\n"
        f"           documents={summary['documents']} golden_questions={summary['golden_questions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
