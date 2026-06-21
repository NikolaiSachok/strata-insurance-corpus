"""Determinism + integrity tests for the generator (the non-negotiable contract).

Same seed -> byte-stable structured output; different seed -> different output;
the model is referentially consistent and the roster covers every entity.
"""

from __future__ import annotations

import pytest

from generator.model import (
    PROFILES,
    build_model,
    index,
    roster_rows,
    to_json_bytes,
    to_roster_bytes,
)


def test_model_json_byte_stable():
    for profile in PROFILES:
        a = to_json_bytes(build_model(42, profile))
        b = to_json_bytes(build_model(42, profile))
        assert a == b, f"model.json not byte-stable for profile={profile}"


def test_roster_byte_stable():
    a = to_roster_bytes(build_model(7, "sample"))
    b = to_roster_bytes(build_model(7, "sample"))
    assert a == b


def test_seed_sensitive():
    assert to_json_bytes(build_model(42, "full")) != to_json_bytes(build_model(43, "full"))


def test_counts_match_profile():
    for profile, counts in PROFILES.items():
        m = build_model(1, profile)
        assert len(m.policyholders) == counts["holders"]
        assert len(m.policies) == counts["policies"]
        assert len(m.claims) == counts["claims"]


def test_referential_integrity():
    m = build_model(99, "full")
    idx = index(m)
    for p in m.policies:
        assert p.holder_id in idx["policyholders"]
        assert p.agent_id in idx["agents"]
    for c in m.claims:
        assert c.policy_id in idx["policies"]
        assert c.adjuster_id in idx["adjusters"]
        # claim date_of_loss falls inside its policy term
        policy = idx["policies"][c.policy_id]
        assert policy.effective_date <= c.date_of_loss <= policy.expiry_date


def test_roster_covers_every_entity():
    m = build_model(3, "sample")
    roster_ids = {r[0] for r in roster_rows(m)}
    expected = (
        {h.id for h in m.policyholders}
        | {a.id for a in m.agents}
        | {a.id for a in m.adjusters}
        | {p.id for p in m.policies}
        | {c.id for c in m.claims}
    )
    assert expected <= roster_ids


def test_contract_docx_byte_stable(tmp_path):
    """The .docx renderer must be byte-reproducible (normalized zip + pinned dates)."""
    from generator.content import contract_document
    from generator.render.docx import write_contract_docx

    m = build_model(42, "slice")
    policy = m.policies[0]
    holder = index(m)["policyholders"][policy.holder_id]
    ctx = contract_document(m.meta, policy, holder)

    a = tmp_path / "a.docx"
    b = tmp_path / "b.docx"
    write_contract_docx(ctx, a)
    write_contract_docx(ctx, b)
    assert a.read_bytes() == b.read_bytes()
    # and it's a valid OOXML package
    import zipfile

    assert "word/document.xml" in zipfile.ZipFile(a).namelist()


def test_declarations_pdf_byte_stable(tmp_path):
    """The PDF render path must be byte-reproducible too (SOURCE_DATE_EPOCH pinned,
    no wall-clock /CreationDate or /ID leaking into WeasyPrint output)."""
    from generator.content import declarations_document
    from generator.model import ANCHOR_EPOCH
    from generator.render.pdf import write_pdf

    m = build_model(42, "slice")
    idx = index(m)
    policy = m.policies[0]
    holder = idx["policyholders"][policy.holder_id]
    agent = idx["agents"][policy.agent_id]
    ctx = declarations_document(m.meta, policy, holder, agent)

    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    try:
        write_pdf("declarations.html.j2", ctx, a, ANCHOR_EPOCH)
    except OSError as e:  # WeasyPrint native libs (cairo/pango) unavailable
        pytest.skip(f"WeasyPrint native libraries unavailable: {e}")
    write_pdf("declarations.html.j2", ctx, b, ANCHOR_EPOCH)
    assert a.read_bytes() == b.read_bytes()


def test_estimate_settlement_amounts_consistent():
    """Estimate net payable == settlement payout == model paid; line items sum to gross."""
    from generator.content import estimate_document, settlement_letter_document

    def _money(s):
        return float(s.replace("€", "").replace(",", ""))

    m = build_model(42, "sample")
    idx = index(m)
    closed = [c for c in m.claims if c.status == "closed"]
    assert closed  # the sample must contain at least one closed claim to exercise this
    for claim in closed:
        policy = idx["policies"][claim.policy_id]
        holder = idx["policyholders"][claim.holder_id]
        adjuster = idx["adjusters"][claim.adjuster_id]
        est = estimate_document(m.meta, claim, policy, holder)
        settle = settlement_letter_document(m.meta, claim, policy, holder, adjuster)

        expected_net = f"€{claim.paid:,.2f}"
        assert est["net_payable"] == expected_net
        assert settle["paid"] == expected_net
        gross = round(claim.paid + policy.deductible, 2)
        assert est["gross_total"] == f"€{gross:,.2f}"
        assert round(sum(_money(a) for _, a in est["rows"]), 2) == gross


def test_xlsx_byte_stable(tmp_path):
    """The .xlsx renderer must be byte-reproducible (normalized zip + pinned modified)."""
    import zipfile

    from generator import tabular
    from generator.render.sheets import write_xlsx

    m = build_model(42, "sample")
    table = tabular.premium_register(m)
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    write_xlsx([table], a)
    write_xlsx([table], b)
    assert a.read_bytes() == b.read_bytes()
    assert "xl/workbook.xml" in zipfile.ZipFile(a).namelist()


def test_aggregation_golden_matches_model():
    """Golden aggregation answers must equal the model-computed totals (single source)."""
    from generator import tabular
    from generator.golden import build_golden

    m = build_model(42, "sample")
    tab_ids = {
        "loss_run": "D1",
        "reserve_register": "D2",
        "premium_register": "D3",
        "commission_summary": "D4",
    }
    golden = build_golden(m, {}, {}, {}, tab_ids)
    agg = {x["id"]: x["answer"] for x in golden if x["query_class"] == "aggregation"}
    assert agg["Q-AGG-open-reserve"] == f"€{tabular.total_open_reserve(m):,.2f}"
    assert agg["Q-AGG-total-premium"] == f"€{tabular.total_annual_premium(m):,.2f}"
    assert agg["Q-AGG-open-claims"] == str(tabular.open_claim_count(m))


def test_knowledge_markdown_deterministic_and_grounded():
    """KB markdown is deterministic, carries the marker, and contains the KB golden answer."""
    from generator import knowledge
    from generator.model import LINE_LABEL, LINES
    from generator.render.markdown import render_markdown

    a = render_markdown(knowledge.underwriting_guidelines())
    b = render_markdown(knowledge.underwriting_guidelines())
    assert a == b
    assert "SYNTHETIC" in a
    # the KB golden answer ("Which lines...") must actually appear in the guidelines text
    assert ", ".join(LINE_LABEL[ln] for ln in LINES) in a


# Every doc type the generator builds today. The committed sample slice must contain
# all of these, so it stays a representative slice as new families land. Add to this set
# (and to the sample) when you add a doc type.
BUILT_DOC_TYPES = {
    "policy_declarations", "policy_contract", "policy_endorsements", "policy_schedule",
    "fnol", "adjuster_report", "estimate", "settlement_letter", "denial_letter",
    "fnol_scanned", "settlement_letter_scanned", "denial_letter_scanned",
    "loss_run", "reserve_register", "premium_register", "commission_summary",
    "underwriting_guidelines", "claims_manual", "customer_faq",
}


def test_sample_profile_covers_all_doc_types(tmp_path):
    """The committed sample slice must exercise every built doc type (representativeness)."""
    import json

    from generator.run import generate

    generate(42, tmp_path / "sample", "sample")
    manifest = json.loads((tmp_path / "sample" / "manifest.json").read_text())
    sample_types = {d["doc_type"] for d in manifest["documents"]}
    missing = BUILT_DOC_TYPES - sample_types
    assert not missing, f"sample slice is missing doc types: {sorted(missing)}"


def test_scan_byte_stable(tmp_path):
    """The scan-effect renderer must be byte-reproducible (seeded effects)."""
    import pathlib

    from generator.render.scan import doc_seed, scan_pdf

    src = pathlib.Path(__file__).resolve().parents[1] / "sample/docs/claim/C-1000-fnol.pdf"
    if not src.exists():
        pytest.skip("committed sample FNOL not present")
    s = doc_seed("DOC-C-1000-FNOL", 42)
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    try:
        scan_pdf(src, a, s)
    except Exception as e:  # pypdfium2 unavailable in this env
        pytest.skip(f"scan renderer unavailable: {e}")
    scan_pdf(src, b, s)
    assert a.read_bytes() == b.read_bytes()


def test_synthetic_markers_present():
    m = build_model(5, "slice")
    assert m.meta["synthetic"] is True
    assert "SYNTHETIC" in m.meta["marker"]
    # every policyholder is in a supported European country with a synthetic national id
    for h in m.policyholders:
        assert h.country in {"DE", "FR", "ES", "IT", "NL", "IE"}
        assert h.national_id


def test_national_ids_are_invalid_dni():
    """ES DNI national ids must carry the WRONG control letter (clearly synthetic)."""
    from generator.identity import _DNI_LETTERS

    m = build_model(11, "full")
    for h in m.policyholders:
        if h.country != "ES":
            continue
        num, letter = h.national_id.split("-")
        assert letter != _DNI_LETTERS[int(num) % 23], f"{h.national_id} has a VALID DNI letter"
