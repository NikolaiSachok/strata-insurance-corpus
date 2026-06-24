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
import json
from pathlib import Path

from .content import (
    accident_statement_document,
    adjuster_report_document,
    cause_label,
    contract_document,
    declarations_document,
    denial_letter_document,
    endorsements_document,
    estimate_base,
    estimate_document,
    fnol_document,
    id_card_document,
    schedule_document,
    settlement_letter_document,
)
from . import CURRENCY_SYMBOL, imageprompts, knowledge, tabular
from .golden import build_golden, write_golden
from .manifest import write_manifest
from .model import ANCHOR_EPOCH, LINE_LABEL, LINES, build_model, index, write_model
from .provenance import Assertion, DocRecord, provenance_index, sha256_file
from .schema import write_schema


def _money(x: float) -> str:
    """Match content._money so manifest provenance values equal the rendered text."""
    return f"{CURRENCY_SYMBOL}{x:,.2f}"


# Generated artifacts removed before each run so regeneration leaves no orphans. The
# `evidence/` dir (non-deterministic AI image pixels) is intentionally NOT listed — it is
# preserved across runs and picked up if present. Anything else (e.g. a committed README.md)
# is preserved too.
_GENERATED = ("docs", "schema", "model.json", "roster.tsv", "manifest.json", "golden.jsonl", "image-prompts.jsonl", "pii-index.jsonl")


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
    evidence_specs: list[dict] = []
    face_specs: list[dict] = []

    if render:
        from .render.docx import write_contract_docx  # lazy imports
        from .render.pdf import write_pdf

        from .render.scan import doc_seed, scan_pdf

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

        def emit_scan(source_rel, source_doc_id, doc_type, entity_ids):
            """Degrade an already-written PDF into a scanned (OCR-target) variant."""
            rel = source_rel.rsplit(".", 1)[0] + "-scanned.jpg"
            scan_pdf(out / source_rel, out / rel, doc_seed(source_doc_id, seed))
            records.append(
                DocRecord(
                    doc_id=f"{source_doc_id}-SCAN",
                    doc_type=doc_type,
                    format="jpg",
                    path=rel,
                    entity_ids=entity_ids,
                    is_scanned=True,
                    sha256=sha256_file(out / rel),
                    source_doc_id=source_doc_id,
                )
            )

        def _face_uri(rel: str) -> str | None:
            """Base64 data-URI for a face image if its pixels exist in this corpus, else None.

            A data-URI keeps the PDF self-contained and byte-stable (no absolute path leaks in,
            no real local filesystem path embedded) and lets the same template render with a
            neutral placeholder when only the prompt-spec (not the pixels) is present."""
            import base64

            p = out / rel
            if not p.exists():
                return None
            return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode("ascii")

        # 2+3. policy family: declarations (PDF), contract (docx), endorsements (PDF), schedule (PDF)
        for policy in model.policies:
            holder = idx["policyholders"][policy.holder_id]
            agent = idx["agents"][policy.agent_id]
            base_ids = [policy.id, policy.holder_id, policy.agent_id]

            # Declarations page (PDF)
            decl_id = f"DOC-{policy.id}-DEC"
            decl_rel = f"docs/policy/{policy.id}-declarations.pdf"
            write_pdf("declarations.html.j2", declarations_document(model.meta, policy, holder, agent), out / decl_rel, ANCHOR_EPOCH)
            decl_asserts = [
                Assertion(policy.id, "annual_premium", _money(policy.annual_premium)),
                Assertion(policy.id, "effective_date", policy.effective_date),
                Assertion(policy.id, "expiry_date", policy.expiry_date),
                Assertion(policy.id, "line", policy.line),
            ]
            if policy.vehicle:  # the declarations page lists the insured vehicle (Motor)
                decl_asserts.append(Assertion(policy.id, "vehicle", f"{policy.vehicle['make']} {policy.vehicle['model']}"))
            records.append(
                DocRecord(
                    doc_id=decl_id,
                    doc_type="policy_declarations",
                    format="pdf",
                    path=decl_rel,
                    entity_ids=base_ids,
                    asserts=decl_asserts,
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

        # Identity family (#11): one on-file ID card per policyholder (real synthetic PII +
        # ICAO MRZ + synthetic portrait) + a scanned variant. The portrait is a separate
        # non-deterministic image tier (prompt-spec committed; pixels for sample/, on-demand
        # for the full set) — the card embeds it when present, else a neutral placeholder.
        for holder in model.policyholders:
            face = imageprompts.face_spec(holder, seed)
            face_specs.append(face)

            idc_id = f"DOC-{holder.id}-IDCARD"
            idc_rel = f"docs/identity/{holder.id}-id-card.pdf"
            emit_pdf(
                idc_id, "id_card", "id_card.html.j2",
                id_card_document(model.meta, holder, _face_uri(face["path"])),
                idc_rel, [holder.id],
                [
                    Assertion(holder.id, "national_id", holder.national_id),
                    Assertion(holder.id, "dob", holder.dob),
                    Assertion(holder.id, "country", holder.country),
                ],
            )
            emit_scan(idc_rel, idc_id, "id_card_scanned", [holder.id])

        # Claim family: FNOL (all) + adjuster report (all) + estimate (open/closed)
        # + settlement letter (closed) | denial letter (denied)
        for claim in model.claims:
            policy = idx["policies"][claim.policy_id]
            holder = idx["policyholders"][claim.holder_id]
            adjuster = idx["adjusters"][claim.adjuster_id]
            claim_ids = [claim.id, claim.policy_id, claim.holder_id, claim.adjuster_id]
            evidence_specs.append(imageprompts.evidence_spec(claim, policy, holder, seed))

            # FNOL
            fnol_id = f"DOC-{claim.id}-FNOL"
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
            emit_scan(f"docs/claim/{claim.id}-fnol.pdf", fnol_id, "fnol_scanned", claim_ids)

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
                emit_pdf(
                    settle_id, "settlement_letter", "settlement_letter.html.j2",
                    settlement_letter_document(model.meta, claim, policy, holder, adjuster),
                    f"docs/claim/{claim.id}-settlement-letter.pdf", claim_ids,
                    [
                        Assertion(claim.id, "paid", _money(claim.paid)),
                        Assertion(claim.id, "status", claim.status),
                    ],
                )
                emit_scan(f"docs/claim/{claim.id}-settlement-letter.pdf", settle_id, "settlement_letter_scanned", claim_ids)
            elif claim.status == "denied":
                denial_id = f"DOC-{claim.id}-DENIAL"
                emit_pdf(
                    denial_id, "denial_letter", "denial_letter.html.j2",
                    denial_letter_document(model.meta, claim, policy, holder, adjuster),
                    f"docs/claim/{claim.id}-denial-letter.pdf", claim_ids,
                    [Assertion(claim.id, "status", "denied")],
                )
                emit_scan(f"docs/claim/{claim.id}-denial-letter.pdf", denial_id, "denial_letter_scanned", claim_ids)

            # Motor accident statement (Motor claims only) + scanned variant
            if policy.line == "personal_auto":
                acc_id = f"DOC-{claim.id}-ACCIDENT"
                emit_pdf(
                    acc_id, "accident_statement", "accident_statement.html.j2",
                    accident_statement_document(model.meta, claim, policy, holder),
                    f"docs/claim/{claim.id}-accident-statement.pdf", claim_ids,
                    [Assertion(claim.id, "line", policy.line)],
                )
                emit_scan(f"docs/claim/{claim.id}-accident-statement.pdf", acc_id, "accident_statement_scanned", claim_ids)

        # Tabular family (corpus-level): registers in xlsx + commission in csv
        from .render.sheets import write_csv, write_xlsx

        # Registers carry the corpus-level aggregate facts they tabulate, so aggregation golden
        # questions resolve to them through provenance (single source of truth).
        tab_specs = [
            ("DOC-TAB-LOSS-RUN", "loss_run", "xlsx", "docs/tabular/loss-run.xlsx",
             lambda p: write_xlsx([tabular.loss_run(model)], p), [c.id for c in model.claims],
             [Assertion("CORPUS", "open_claim_count", str(tabular.open_claim_count(model)))]),
            ("DOC-TAB-RESERVE", "reserve_register", "xlsx", "docs/tabular/reserve-register.xlsx",
             lambda p: write_xlsx([tabular.reserve_register(model)], p), [c.id for c in model.claims if c.status == "open"],
             [Assertion("CORPUS", "total_open_reserve", _money(tabular.total_open_reserve(model)))]),
            ("DOC-TAB-PREMIUM", "premium_register", "xlsx", "docs/tabular/premium-register.xlsx",
             lambda p: write_xlsx([tabular.premium_register(model)], p), [p.id for p in model.policies],
             [Assertion("CORPUS", "total_annual_premium", _money(tabular.total_annual_premium(model)))]),
            ("DOC-TAB-COMMISSION", "commission_summary", "csv", "docs/tabular/commission-summary.csv",
             lambda p: write_csv(tabular.commission_summary(model), p), [a.id for a in model.agents], []),
        ]
        for doc_id, doc_type, fmt, rel, writer, entity_ids, asserts in tab_specs:
            writer(out / rel)
            records.append(
                DocRecord(
                    doc_id=doc_id, doc_type=doc_type, format=fmt, path=rel,
                    entity_ids=entity_ids, asserts=asserts, sha256=sha256_file(out / rel),
                )
            )

        # Knowledge base (corpus-level reference docs): markdown + docx
        from .render.docx import write_sections_docx
        from .render.markdown import write_markdown

        kb_specs = [
            ("DOC-KB-UW", "underwriting_guidelines", "md", "docs/kb/underwriting-guidelines.md",
             lambda p: write_markdown(knowledge.underwriting_guidelines(), p),
             [Assertion("CORPUS", "lines_of_business", ", ".join(LINE_LABEL[ln] for ln in LINES))]),
            ("DOC-KB-CLAIMS", "claims_manual", "docx", "docs/kb/claims-handling-manual.docx",
             lambda p: write_sections_docx(knowledge.claims_manual(), p), []),
            ("DOC-KB-FAQ", "customer_faq", "md", "docs/kb/customer-faq.md",
             lambda p: write_markdown(knowledge.customer_faq(), p), []),
        ]
        for doc_id, doc_type, fmt, rel, writer, asserts in kb_specs:
            writer(out / rel)
            records.append(
                DocRecord(
                    doc_id=doc_id, doc_type=doc_type, format=fmt, path=rel,
                    entity_ids=[], asserts=asserts, sha256=sha256_file(out / rel),
                )
            )

        # Generated-image tier (#11): commit the deterministic prompt-spec for every claim
        # evidence photo and every policyholder ID portrait; the pixels are a separate
        # non-deterministic tier (rendered for sample/, on-demand for the HF release). A manifest
        # record always exists; rendered=True only if the pixel file is already present.
        image_specs = [(s, "evidence_photo", s["claim_id"]) for s in evidence_specs]
        image_specs += [(s, "id_photo", s["holder_id"]) for s in face_specs]
        image_specs.sort(key=lambda t: t[0]["doc_id"])
        (out / "image-prompts.jsonl").write_bytes(
            ("\n".join(json.dumps(s, sort_keys=True, ensure_ascii=False) for s, _, _ in image_specs) + "\n").encode("utf-8")
            if image_specs
            else b""
        )
        for spec, doc_type, entity_id in image_specs:
            pixel = out / spec["path"]
            rendered = pixel.exists()
            records.append(
                DocRecord(
                    doc_id=spec["doc_id"],
                    doc_type=doc_type,
                    format="jpg",
                    path=spec["path"],
                    entity_ids=[entity_id],
                    is_generated=True,
                    rendered=rendered,
                    sha256=sha256_file(pixel) if rendered else "",
                    prompt_spec=spec,
                )
            )

    # 4. manifest
    write_manifest(out, model.meta, records)

    # 4b. redaction ground-truth index (#12): every PII span in every document, so a consuming
    # RAG redaction layer can be scored. Pure function of the model -> deterministic; empty under
    # --no-render (no document records exist yet).
    from .pii import build_pii_index, write_pii_index

    pii_spans = build_pii_index(model, records)
    write_pii_index(out, pii_spans)

    # 5. golden — every question resolved through the provenance index (#13): its answer is the
    # asserted value and its relevant docs are exactly those asserting the fact.
    golden = build_golden(model, provenance_index(records))
    write_golden(out, golden)

    return {
        "out": str(out),
        "model": paths["model"],
        "roster": paths["roster"],
        "documents": len(records),
        "golden_questions": len(golden),
        "pii_spans": len(pii_spans),
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
        f"           documents={summary['documents']} golden_questions={summary['golden_questions']} pii_spans={summary['pii_spans']}"
    )
    return 0


def _pin_hash_seed() -> None:
    """Re-exec once with PYTHONHASHSEED=0 so the corpus is byte-stable across processes.

    Some Faker locale providers (e.g. it_IT city) pick from sets whose iteration order is
    PYTHONHASHSEED-dependent; without a fixed hash seed model.json varies run-to-run.
    Hash randomization is fixed at interpreter start, so we must re-exec to set it.
    """
    import os
    import sys

    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable, "-m", "generator.run", *sys.argv[1:]])


if __name__ == "__main__":
    import os
    import sys

    _pin_hash_seed()
    _rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Bypass interpreter teardown: weasyprint/fontconfig can segfault during native cleanup at
    # exit (after all documents are written). os._exit avoids that without affecting the output.
    os._exit(_rc)
