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
    cause_label,
    contract_document,
    declarations_document,
    endorsements_document,
    fnol_document,
    schedule_document,
)
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

    if render:
        from .render.docx import write_contract_docx  # lazy imports
        from .render.pdf import write_pdf

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

        # FNOL per claim
        for claim in model.claims:
            policy = idx["policies"][claim.policy_id]
            holder = idx["policyholders"][claim.holder_id]
            adjuster = idx["adjusters"][claim.adjuster_id]
            ctx = fnol_document(model.meta, claim, policy, holder, adjuster)
            doc_id = f"DOC-{claim.id}-FNOL"
            rel = f"docs/claim/{claim.id}-fnol.pdf"
            write_pdf("fnol.html.j2", ctx, out / rel, ANCHOR_EPOCH)
            fnol_doc_for_claim[claim.id] = doc_id
            records.append(
                DocRecord(
                    doc_id=doc_id,
                    doc_type="fnol",
                    format="pdf",
                    path=rel,
                    entity_ids=[claim.id, claim.policy_id, claim.holder_id, claim.adjuster_id],
                    asserts=[
                        Assertion(claim.id, "cause", cause_label(claim.cause)),
                        Assertion(claim.id, "date_of_loss", claim.date_of_loss),
                        Assertion(claim.id, "status", claim.status),
                    ],
                    sha256=sha256_file(out / rel),
                )
            )

    # 4. manifest
    write_manifest(out, model.meta, records)

    # 5. golden
    golden = build_golden(model, fnol_doc_for_claim, decl_doc_for_policy)
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
